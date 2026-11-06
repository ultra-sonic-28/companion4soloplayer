# Slugify

`Slugify` converts an arbitrary string into a portable, file-system- and
URL-safe slug. It strips accents, lowercases the text (optionally),
replaces every run of problematic characters with a configurable separator,
and guards against reserved Windows names and over-long results.

## Class diagram
```plantuml format="svg" source="docs/assets/diagrams/classes_companion4soloplayer_utils_slugify.plantuml"
```

## API reference

::: utils.slugify