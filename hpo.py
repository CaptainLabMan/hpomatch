import re
from collections import defaultdict
from functools import cache
import pandas as pd

def create_genes_x_phenotypes_matrix(phenotype_to_genes_df: pd.DataFrame) -> pd.DataFrame:
    '''
    Возвращает DF:
    Гены x Все терминины (hpo_id)
    '''
    return (
        pd.crosstab(phenotype_to_genes_df['gene_symbol'], phenotype_to_genes_df['hpo_id'])
        .gt(0)
        .astype('uint8')
        )


def match_genes_to_hpo_ids(
        genes_x_phenotypes_matrix: pd.DataFrame,
        hpo_ids: list[str]
) -> pd.DataFrame:
    '''
    Возвращает DF:
    Гены x Совпавшие терминины (hpo_id)
    '''
    
    matches = genes_x_phenotypes_matrix.reindex(
        columns=list(dict.fromkeys(hpo_ids)),
        fill_value=0,
        )
    return matches[matches.ne(0).any(axis=1)]


def count_matches(genes_x_phenotypes_matrix_matches: pd.DataFrame) -> pd.DataFrame:
    '''
    Возвращает DF:
    Ген | Количество совпадений терминов гена
    '''

    return (
        genes_x_phenotypes_matrix_matches.sum(axis=1)
        .to_frame(name='matches_count')
        .reset_index()
    )


def get_gene_match_summary(
        genes_x_phenotypes_matrix_matches: pd.DataFrame,
        phenotype_to_genes_df: pd.DataFrame,
) -> pd.DataFrame:
    '''
    Возвращает DF:
    Ген | Кол-во совпадений предоставленых терминов среди терминов гена (hpo_id) | Список совпавших терминов (hpo_name)
    '''

    names = (
        phenotype_to_genes_df
        .drop_duplicates("hpo_id")
        .set_index("hpo_id")["hpo_name"]
        .to_dict()
    )

    stats = count_matches(genes_x_phenotypes_matrix_matches)

    stats["matched_terms"] = [
        ", ".join(names[hpo_id] for hpo_id in row.index[row.eq(1)])
        for _, row in genes_x_phenotypes_matrix_matches.iterrows()
    ]

    return stats


def get_genes_stats_by_count_matches(matches_counts: pd.DataFrame,):
    '''
    Возвращает DF:
    Кол-во совпадений предоставленых терминов среди терминов гена (hpo_id) | Кол-во генов | Список генов 
    '''

    return (
        matches_counts
        .groupby('matches_count', as_index=False)
        .agg(
            genes_count=('gene_symbol', 'count'),
            genes=('gene_symbol', ', '.join),
        )
        .sort_values('matches_count', ascending=False)
    )


# ==================================================================================================================================


def build_gene_phenotypes_dict(
    genes_to_disease_df: pd.DataFrame,
    disease_annotations: pd.DataFrame,
    hp: dict,
) -> dict:
    """
    Build a dictionary of genes, associated diseases, and grouped HPO terms.

    Args:
        genes_to_disease_df: Data loaded from genes_to_disease.txt.
        disease_annotations: Data loaded from phenotype.hpoa.
        hp: Parsed contents of hp.json.

    Returns:
        A dictionary with the following structure (illustrative data):

        {
            "GENE1": {
                "diseases": {
                    "OMIM:123456": {
                        "name": "Disease name",
                        "inheritance": "Autosomal recessive inheritance",
                        "groups": {
                            "HP:0000152": {
                                "name": "Head or neck",
                                "terms": {
                                    "HP:0000218": {
                                        "name": "High palate",
                                        "frequency": "1/4",
                                        "excluded": False
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        inheritance: Inheritance labels separated by "; ".
            Uses "Нет данных" when no inheritance annotation is available.
        frequency: Frequency label or original value, such as "1/4".
            Distinct values from repeated annotations are joined with "; ".
            Uses None when frequency is not provided.
        excluded: True when the annotation has qualifier="NOT".

        A term may appear in multiple groups because HPO allows
        multiple parents. Onset information is not included.
    """

    # Extract the ontology graph from the HPO JSON file.
    graph = hp["graphs"][0]

    def to_id(value):
        # Convert an ontology URL to an ID:
        # http://purl.obolibrary.org/obo/HP_0001252 -> HP:0001252
        return value.rsplit("/", 1)[-1].replace("_", ":")

    # Map each term ID to its readable name.
    names = {
        to_id(node["id"]): node["lbl"]
        for node in graph["nodes"]
        if "lbl" in node
    }

    # Map each term to its immediate parents.
    parents = defaultdict(set)

    for edge in graph["edges"]:
        if edge["pred"] == "is_a":
            parents[to_id(edge["sub"])].add(to_id(edge["obj"]))

    def clean_group_name(name):
        # Remove generic wording from group names.
        name = re.sub(
            r"^abnormality of (?:the )?|\babnormality\b",
            "",
            name,
            flags=re.IGNORECASE,
        )

        # Remove extra spaces and capitalize the first letter.
        name = " ".join(name.split())
        return name[:1].upper() + name[1:]

    # Use the immediate children of "Phenotypic abnormality"
    # as the main phenotype groups.
    categories = {
        term: clean_group_name(names[term])
        for term, parent_ids in parents.items()
        if "HP:0000118" in parent_ids
    }

    # Handle "Mode of inheritance" separately from phenotype groups.
    inheritance_id = "HP:0000005"

    @cache
    def find_groups(hpo_id):
        # Cache results so repeated terms do not require another traversal.
        found = set()
        visited = set()
        pending = [hpo_id]

        # Walk upward through all parents to find matching groups.
        while pending:
            term = pending.pop()

            if term in visited:
                continue

            visited.add(term)

            if term in categories or term == inheritance_id:
                found.add(term)

            pending.extend(parents.get(term, ()))

        return sorted(found)

    # Build disease records once before linking them to genes.
    diseases = {}

    for row in disease_annotations.fillna("").itertuples(index=False):
        # Create a disease record if it does not already exist.
        disease = diseases.setdefault(
            row.database_id,
            {
                "name": row.disease_name,
                "inheritance": [],
                "groups": {},
            },
        )

        term_name = names.get(row.hpo_id, row.hpo_id)
        group_ids = find_groups(row.hpo_id)

        # Collect unique inheritance labels, excluding NOT annotations.
        if inheritance_id in group_ids:
            if (
                row.qualifier != "NOT"
                and term_name not in disease["inheritance"]
            ):
                disease["inheritance"].append(term_name)

        # Translate frequency HPO IDs into names.
        # Keep fractions and percentages unchanged; use None if missing.
        frequency = str(row.frequency).strip()
        frequency = (
            names.get(frequency, frequency)
            if frequency not in ("", "-")
            else None
        )

        for group_id in group_ids:
            # Inheritance is stored at disease level, not as a group.
            if group_id == inheritance_id:
                continue

            group = disease["groups"].setdefault(
                group_id,
                {
                    "name": categories[group_id],
                    "terms": {},
                },
            )

            # Use the HPO ID as the key to avoid duplicate term entries.
            term = group["terms"].setdefault(
                row.hpo_id,
                {
                    "name": term_name,
                    "frequency": None,
                    "excluded": row.qualifier == "NOT",
                },
            )

            # Preserve distinct frequencies from repeated annotations.
            # These values are displayed together, not combined statistically.
            if frequency:
                frequencies = (
                    term["frequency"].split("; ")
                    if term["frequency"]
                    else []
                )

                if frequency not in frequencies:
                    frequencies.append(frequency)

                term["frequency"] = "; ".join(frequencies)

    for disease in diseases.values():
        # Convert the inheritance list into a display string.
        disease["inheritance"] = (
            "; ".join(disease["inheritance"]) or "Нет данных"
        )

        # Sort phenotype groups alphabetically by their display names.
        disease["groups"] = dict(
            sorted(
                disease["groups"].items(),
                key=lambda item: item[1]["name"],
            )
        )

    # Keep unique gene–disease pairs.
    links = (
        genes_to_disease_df[["gene_symbol", "disease_id"]]
        .fillna("")
        .drop_duplicates()
    )

    # Build the final dictionary with gene symbols as top-level keys.
    result = {}

    for gene, disease_id in links.itertuples(index=False, name=None):
        # Skip links without a usable gene symbol or disease ID.
        if gene in ("", "-") or disease_id in ("", "-"):
            continue

        gene_data = result.setdefault(gene, {"diseases": {}})

        # Reuse the disease record if annotations are available.
        # Otherwise, retain the disease ID with empty phenotype groups.
        gene_data["diseases"][disease_id] = diseases.get(
            disease_id,
            {
                "name": disease_id,
                "inheritance": "Нет данных",
                "groups": {},
            },
        )

    return result

# ==================================================================================================================================
# Prepare hpo search terms
# ==================================================================================================================================

def prepare_hpo_search_terms(
    phenotype_to_genes_df: pd.DataFrame,
    hp: dict,
) -> list[dict]:

    synonyms = {
        node["id"].rsplit("/", 1)[-1].replace("_", ":"): [
            item["val"]
            for item in node.get("meta", {}).get("synonyms", [])
        ]
        for node in hp["graphs"][0]["nodes"]
    }

    terms = (
        phenotype_to_genes_df[["hpo_id", "hpo_name"]]
        .drop_duplicates("hpo_id")
    )

    result = []

    for hpo_id, hpo_name in terms.itertuples(index=False, name=None):
        names = [hpo_name, *synonyms.get(hpo_id, [])]

        for name in dict.fromkeys(names):
            result.append({
                "hpo_id": hpo_id,
                "hpo_name": hpo_name,
                "name": name,
            })

    return result