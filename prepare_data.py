from pathlib import Path
import json
import pandas as pd

from utils import fetch_file
from hpo import (
    create_genes_x_phenotypes_matrix,
    create_diseases_x_phenotypes_matrix,
    build_gene_phenotypes_dict,
    prepare_hpo_search_terms
    )

# ==============================================================================================================
# Settings
# ==============================================================================================================
main_path = Path.cwd()
hpo_dir = main_path / 'data/hpo'
static_data_dir = main_path / 'static/data'
output_dir = main_path / 'data/output'

# ==============================================================================================================
# Donwload files
# ==============================================================================================================
base_hpo_url = "https://github.com/obophenotype/human-phenotype-ontology/releases/latest/download"
hpo_urls = {
    'phenotype_to_genes.txt': f'{base_hpo_url}/phenotype_to_genes.txt',
    'genes_to_phenotype.txt': f'{base_hpo_url}/genes_to_phenotype.txt',
    'genes_to_disease.txt': f'{base_hpo_url}/genes_to_disease.txt',
    'phenotype.hpoa': f'{base_hpo_url}/phenotype.hpoa',
    'hp.json': f'{base_hpo_url}/hp.json',
}

for url in hpo_urls:
    fetch_file(hpo_urls[url], hpo_dir)

# ==============================================================================================================
# Prepare data
# ==============================================================================================================

# --------------------------------------------------------------------------------------------------------------
# Prepare genes_x_phenotypes_matrix
# --------------------------------------------------------------------------------------------------------------
phenotype_to_genes_df = pd.read_csv(hpo_dir / 'phenotype_to_genes.txt', sep='\t')
genes_x_phenotypes_matrix = create_genes_x_phenotypes_matrix(phenotype_to_genes_df)
genes_x_phenotypes_matrix.to_pickle(static_data_dir / 'genes_x_phenotypes_matrix.pkl.gz')

# --------------------------------------------------------------------------------------------------------------
# Prepare diseases_x_phenotypes_matrix
# --------------------------------------------------------------------------------------------------------------
phenotypes_df = pd.read_csv(
    hpo_dir / "phenotype.hpoa",
    sep="\t",
    comment="#",
    dtype=str,
    keep_default_na=False,
)
diseases_x_phenotypes_matrix = create_diseases_x_phenotypes_matrix(phenotypes_df)
diseases_x_phenotypes_matrix.to_pickle(static_data_dir / 'diseases_x_phenotypes_matrix.pkl.gz')

# --------------------------------------------------------------------------------------------------------------
# Prepare gene_phenotypes_dict
# --------------------------------------------------------------------------------------------------------------
genes_to_disease_df = pd.read_csv(
    hpo_dir / 'genes_to_disease.txt',
    sep="\t",
    dtype=str,
    keep_default_na=False,
)

disease_annotations = pd.read_csv(
    hpo_dir / 'phenotype.hpoa',
    sep="\t",
    comment="#",
    dtype=str,
    keep_default_na=False,
)

with open(hpo_dir / 'hp.json', encoding='utf-8') as file:
    hp = json.load(file)

data = build_gene_phenotypes_dict(
    genes_to_disease_df,
    disease_annotations,
    hp,
)

with open(static_data_dir / 'gene_phenotypes.json', 'w', encoding='utf-8') as file:
    json.dump(data, file, ensure_ascii=False, indent=2)

# --------------------------------------------------------------------------------------------------------------
# Prepare hpo search terms
# --------------------------------------------------------------------------------------------------------------

with open(hpo_dir / 'hp.json', encoding='utf-8') as file:
    hp = json.load(file)

hpo_ids = (
    genes_x_phenotypes_matrix.columns
    .union(diseases_x_phenotypes_matrix.columns)
    .tolist()
)

terms = prepare_hpo_search_terms(hpo_ids, hp)

with open(static_data_dir / 'hpo_terms.json', "w", encoding='utf-8') as file:
    json.dump(terms, file, ensure_ascii=False)