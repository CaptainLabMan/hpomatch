function referenceUrl(reference) {
    const prefixes = {
        "PMID:": "https://pubmed.ncbi.nlm.nih.gov/",
        "OMIM:": "https://omim.org/entry/",
        "ORPHA:": "https://www.orpha.net/en/disease/detail/"
    };

    for (const [prefix, base] of Object.entries(prefixes)) {
        if (reference.startsWith(prefix)) {
            return base + encodeURIComponent(reference.slice(prefix.length));
        }
    }

    if (/^https?:\/\//i.test(reference)) return reference;

    return null;
}

document.querySelectorAll(".symptom").forEach(element => {
    const content = document.createElement("div");
    const references = JSON.parse(element.dataset.references);

    if (!references.length) content.textContent = "No sources available.";

    for (const reference of references) {
        const row = document.createElement("div");
        const url = referenceUrl(reference);

        if (url) {
            const link = document.createElement("a");
            link.href = url;
            link.textContent = reference;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            row.append(link);
        } else {
            row.textContent = reference;
        }

        content.append(row);
    }

    const popover = new bootstrap.Popover(element, {
        container: "body",
        trigger: "manual",
        placement: "auto",
        html: true,
        animation: false,
        title: element.dataset.hpoId,
        content: content
    });

    let timer;
    let popup;

    function show() {
        clearTimeout(timer);
        popover.show();
    }

    function scheduleHide() {
        clearTimeout(timer);

        timer = setTimeout(() => {
            if (element.matches(":hover, :focus-within")) return;
            if (popup?.matches(":hover, :focus-within")) return;

            popover.hide();
        }, 200);
    }

    element.addEventListener("mouseenter", show);
    element.addEventListener("mouseleave", scheduleHide);
    element.addEventListener("focusin", show);
    element.addEventListener("focusout", scheduleHide);

    element.addEventListener("inserted.bs.popover", () => {
        popup = document.getElementById(
            element.getAttribute("aria-describedby")
        );

        popup.addEventListener("mouseenter", () => clearTimeout(timer));
        popup.addEventListener("mouseleave", scheduleHide);
        popup.addEventListener("focusin", () => clearTimeout(timer));
        popup.addEventListener("focusout", scheduleHide);
    });
});