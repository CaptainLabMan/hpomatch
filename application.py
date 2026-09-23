from pathlib import Path
import json
import pandas as pd

from fastapi import FastAPI, Request, Body, Query, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from hpo import (
    match_genes_to_hpo_ids,
    get_gene_match_summary,
    get_genes_stats_by_count_matches,
)


# Resolve paths relative to this file.
BASE_DIR = Path(__file__).resolve().parent

# ==================================================================================================================================

# ==================================================================================================================================
matrix = pd.read_pickle(
    BASE_DIR / "static/data/genes_x_phenotypes_matrix.pkl"
)

phenotype_names = pd.read_csv(
    BASE_DIR / "data/hpo/phenotype_to_genes.txt",
    sep="\t",
    usecols=["hpo_id", "hpo_name"],
).drop_duplicates("hpo_id")

# ==================================================================================================================================

# ==================================================================================================================================
with (BASE_DIR / "static/data/gene_phenotypes.json").open(
    encoding="utf-8"
) as file:
    gene_phenotypes = json.load(file)

# Match case-insensitively while preserving symbols such as C9orf72.
gene_symbols = {gene.upper(): gene for gene in gene_phenotypes}


def get_gene_data(gene: str):
    gene = gene_symbols.get(gene.strip().upper())

    if gene is None:
        return None

    diseases = gene_phenotypes[gene]["diseases"]

    # Collect all symptom groups across the gene's diseases.
    groups = {
        group_id: group["name"]
        for disease in diseases.values()
        for group_id, group in disease["groups"].items()
    }

    return {
        "gene": gene,
        "diseases": diseases,
        "groups": dict(sorted(groups.items(), key=lambda item: item[1])),
    }

# ==================================================================================================================================

# ==================================================================================================================================
app = FastAPI(title="PhenFind")

# Serve CSS, JavaScript, and images.
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

# Configure HTML templates.
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
    )


@app.post("/matches")
def get_matches(
    hpo_ids: list[str] = Body(...),
    min_matches: int = Query(1, ge=1),
):
    matches = match_genes_to_hpo_ids(matrix, hpo_ids)

    matches = matches.loc[
        matches.sum(axis=1) >= min_matches
    ]

    summary = get_gene_match_summary(matches, phenotype_names)
    summary = summary.sort_values("matches_count", ascending=False)

    stats = get_genes_stats_by_count_matches(summary)

    table_options = {
        "index": False,
        "border": 0,
        "classes": "table table-sm table-striped text-center align-middle",
        "justify": "center",
    }

    return {
        "genes": matches.index.tolist(),

        "summary_html": summary.rename(columns={
            "gene_symbol": "Gene",
            "matches_count": "Matches",
            "matched_terms": "Matched terms",
        }).to_html(**table_options),

        "stats_html": stats.rename(columns={
            "matches_count": "Matches",
            "genes_count": "Gene count",
            "genes": "Genes",
        }).to_html(**table_options),
    }


@app.get("/api/genes/{gene}")
def gene_api(gene: str):
    data = get_gene_data(gene)

    if data is None:
        raise HTTPException(status_code=404, detail="Gene not found")

    return data


@app.get("/gene", response_class=HTMLResponse)
def gene_page(request: Request, gene: str):
    data = get_gene_data(gene)

    return templates.TemplateResponse(
        request=request,
        name="gene.html",
        context={
            "gene": data["gene"] if data else gene.strip().upper(),
            "data": data,
        },
        status_code=404 if data is None else 200,
    )