const selectedTerms = new Map();

// Use these IDs for gene matching.
function getSelectedHpoIds() {
    return [...selectedTerms.keys()];
}

function addTerm(term) {
    if (selectedTerms.has(term.hpo_id)) return;

    selectedTerms.set(term.hpo_id, term.hpo_name);

    const tag = $("<span>", {
        class: "badge text-bg-secondary d-inline-flex align-items-center m-1",
        title: term.hpo_id
    });

    $("<span>", {
        class: "text-wrap text-start",
        text: term.hpo_name
    }).appendTo(tag);

    $("<button>", {
        type: "button",
        class: "btn-close btn-close-white ms-2",
        "aria-label": `Remove ${term.hpo_name}`
    }).on("click", function () {
        selectedTerms.delete(term.hpo_id);
        tag.remove();

        // Update results after removing a term.
        updateMatches();

        document.getElementById("search-input")
            .dispatchEvent(new Event("input"));
    }).appendTo(tag);

    $("#selected-terms").append(tag);

    // Update results after adding a term.
    updateMatches();
}

async function initTermSearch() {
    const response = await fetch("/static/data/hpo_terms.json");

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    const terms = await response.json();
    const input = document.getElementById("search-input");
    const exact = document.getElementById("exact-match");

    const autocomplete = new autoComplete({
        selector: "#search-input",
        debounce: 150,
        query: value => value.trim(),

        data: {
            src: terms,
            keys: ["name", "hpo_id"],

            // Hide selected terms and duplicate IDs.
            filter: results => {
                const seen = new Set();

                return results.filter(result => {
                    const id = result.value.hpo_id;

                    if (selectedTerms.has(id) || seen.has(id)) {
                        return false;
                    }

                    seen.add(id);
                    return true;
                });
            }
        },

        searchEngine: (query, record) => {
            query = query.toLowerCase();
            record = record.toLowerCase();

            return exact.checked
                ? record === query
                : record.includes(query);
        },

        resultsList: {
            maxResults: Infinity,
            class: "list-unstyled position-absolute w-100 shadow mt-1 bg-white rounded-3",
            element: list => {
                list.style.cssText =
                    "max-height: 250px; overflow-y: auto; z-index: 1050;";
            }
        },

        resultItem: {
            class: "list-group-item list-group-item-action",
            selected: "active",

            element: (item, result) => {
                const term = result.value;
                const text = `${term.name} — ${term.hpo_id}`;
                const query = input.value.trim();
                const position = text.toLowerCase().indexOf(query.toLowerCase());

                item.replaceChildren();

                if (position === -1) {
                    item.textContent = text;
                    return;
                }

                const mark = document.createElement("mark");
                mark.className = "bg-warning p-0";
                mark.textContent = text.slice(position, position + query.length);

                item.append(
                    document.createTextNode(text.slice(0, position)),
                    mark,
                    document.createTextNode(text.slice(position + query.length))
                );
            }
        },

        events: {
            input: {
                selection: event => {
                    addTerm(event.detail.selection.value);

                    // Refresh suggestions after the library closes the list.
                    queueMicrotask(() => autocomplete.start());
                }
            }
        }
    });

    autocomplete.wrapper.classList.add("position-relative", "flex-shrink-0");

    exact.addEventListener("change", () => autocomplete.start());
}

initTermSearch().catch(error => {
    console.error(error);
    $("#selected-terms").text("Failed to load term search.");
});


let matchRequest = 0;

async function updateMatches() {
    const requestId = ++matchRequest;
    const minimum = document.getElementById("min-matches");
    if (!minimum.checkValidity()) return;
    const ids = getSelectedHpoIds();
    const panels = $("#matching-genes, #gene-match-summary, #genes-match-stats");

    panels.empty();
    if (!ids.length) return;

    panels.text("Loading...");

    try {
        const response = await fetch(`/matches?min_matches=${minimum.valueAsNumber}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(ids)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // Ignore responses for an outdated selection.
        if (requestId !== matchRequest) return;

        if (!data.genes.length) {
            $("#matching-genes").text("Genes: 0");
            $("#gene-match-summary, #genes-match-stats")
                .text("No matching genes.");
            return;
        }

        $("#matching-genes").empty().append(
            $("<h6>", {
                text: `Genes: ${data.genes.length}`
            }),
            $("<div>", {
                text: data.genes.join(", ")
            })
        );
        $("#gene-match-summary").html(data.summary_html);
        $("#genes-match-stats").html(data.stats_html);

    } catch (error) {
        if (requestId !== matchRequest) return;

        panels.text("Failed to load matches.");
        console.error(error);
    }
}

$("#min-matches").on("input", updateMatches);