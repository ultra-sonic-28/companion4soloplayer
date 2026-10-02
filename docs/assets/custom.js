/* Custom JavaScript for Companion4SoloPlayer */
document.addEventListener('DOMContentLoaded', function() {
    const footer = document.querySelector('footer');
    footer.innerHTML = `
    <div class="md-footer-meta md-typeset">
        <div class="md-footer-meta__inner md-grid">
            <div class="md-copyright">
                Made with
                <a href="https://squidfunk.github.io/mkdocs-material/" target="_blank" rel="noopener">
                    Material for MkDocs
                </a>
                and
                <a href="https://mkdocstrings.github.io/" target="_blank" rel="noopener">
                mkdocstrings
                </a>
            </div>
            <span class="md-copyright c-white">Companion4SoloPlayer <i>v0.1.0</i></span>
        </div>
    </div>
`;
});
