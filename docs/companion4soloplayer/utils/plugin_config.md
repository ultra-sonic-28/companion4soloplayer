# Plugin configuration

Each plugin may ship an optional ``datas/config.yaml`` file in its
``datas/`` data directory (same location as the ``plugin.yaml``
manifest). The file declares how the plugin wants its features to
behave inside the application (dialog sizes, plugin version, ...) without
any code change: the values are plain YAML data, read when the plugin is
loaded and published in the :class:`PluginConfigRegistry`.

The registry is a singleton (same pattern as
:class:`~companion4soloplayer.utils.resource_manager.ResourceManager`),
so a configuration loaded once by
:class:`~companion4soloplayer.utils.plugin_loader.PluginLoader` is
reachable from anywhere in the application, whatever its context::

    size = PluginConfigRegistry.instance().character_creation_dialog_size()
    version = PluginConfigRegistry.instance().plugin_version()

## Document shape

```yaml
version: '1.0.0'
dialog:
  - character_creation_dialog:
    width: 860
    height: 800
    attributes_columns: 3
```

Every section is optional: a missing file, a missing section or a
missing entry falls back on the application default.

## Plugin version

The ``version`` entry follows [semantic versioning](https://semver.org/)
(``MAJOR.MINOR.PATCH``). Each component must be a non-negative integer
without leading zeros. Pre-release and build metadata (e.g.
``1.0.0-beta``, ``1.0.0+build``) are not accepted; plugins should use
stable releases.

When the entry is missing, empty or invalid, the application falls back
on ``0.0.0``.

## Class diagram
```plantuml format="svg" source="docs/assets/diagrams/classes_companion4soloplayer_utils_plugin_config.plantuml"
```

## API reference

::: utils.plugin_config