#------------------------------------------------------------------------------
# Copyright (c) 2013, Nucleic Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#------------------------------------------------------------------------------
import warnings

from atom.api import Atom, Typed

from .extension_object import ExtensionObject
from .extension_registry import ExtensionRegistry
from .plugin import Plugin
from .plugin_manifest import create_manifest


class Workbench(Atom):
    """ A base class for creating plugin-style applications.

    This class is used for managing the lifecycle of plugins. It does
    not provide any UI functionality. Such behavior must be supplied
    by a subclass, such as the enaml.studio.Studio class.

    """
    def register(self, data):
        """ Register a plugin with the workbench.

        Parameters
        ----------
        data : str or unicode
            The JSON plugin manifest data. If this is a str, it must be
            encoded in UTF-8 or plain ASCII.

        """
        manifest = create_manifest(data)
        plugin_id = manifest.id
        if plugin_id in self._manifests:
            msg = "The plugin '%s' is already registered. "
            msg += "The duplicate plugin will be ignored."
            warnings.warn(msg % plugin_id)
        else:
            self._manifests[plugin_id] = manifest
        self._registry.add_extension_points(manifest.extension_points)
        self._registry.add_extensions(manifest.extensions)

    def unregister(self, plugin_id):
        """ Remove a plugin from the workbench.

        This will remove the extension points and extensions from the
        workbench, and stop the plugin if it was activated.

        Parameters
        ----------
        plugin_id : unicode
            The identifier of the plugin of interest.

        """
        manifest = self._manifests.pop(plugin_id, None)
        if manifest is None:
            msg = "plugin '%s' is not registered"
            warnings.warn(msg % plugin_id)
            return
        plugin = self._plugins.pop(plugin_id, None)
        if plugin is not None:
            plugin.stop()
            plugin.workbench = None
            plugin.manifest = None
        self._registry.remove_extensions(manifest.extensions)
        self._registry.remove_extension_points(manifest.extension_points)

    def get_manifest(self, plugin_id):
        """ Get the plugin manifest for a given plugin id.

        Parameters
        ----------
        plugin_id : unicode
            The identifier of the plugin of interest.

        Returns
        -------
        result : PluginManifest or None
            The manifest for the plugin of interest, or None if it does
            not exist.

        """
        return self._manifests.get(plugin_id)

    def get_plugin(self, plugin_id, force_create=True):
        """ Get the plugin object for a given plugin id.

        Parameters
        ----------
        plugin_id : unicode
            The identifier of the plugin of interest.

        force_create : bool, optional
            Whether to automatically import and start the plugin object
            if it is not already active. The default is True.

        Returns
        -------
        result : Plugin or None
            The plugin of interest, or None if it does not exist and/or
            could not be created.

        """
        if plugin_id in self._plugins:
            return self._plugins[plugin_id]
        manifest = self._manifests.get(plugin_id)
        if manifest is None:
            msg = "plugin manifest for plugin '%s' is not registered"
            warnings.warn(msg % plugin_id)
            return None
        if not force_create:
            return None
        plugin = self._create_plugin(manifest)
        self._plugins[plugin_id] = plugin
        if plugin is None:
            return None
        plugin.manifest = manifest
        plugin.workbench = self
        plugin.start()
        return plugin

    def create_extension_object(self, extension):
        """ Create the implementation object for a given extension.

        This will cause the extension's plugin class to be imported
        and activated unless the plugin is already active.

        Parameters
        ----------
        extension : Extension
            The extension which contains the path to the object class.

        Returns
        -------
        result : ExtensionObject or None
            The newly created extension object, or None if one could
            not be created.

        """
        self.get_plugin(extension.plugin_id)  # ensure plugin is activated
        obj = self._create_extension_object(extension)
        if obj is None:
            return None
        obj.workbench = self
        obj.extension = extension
        obj.initialize()
        return obj

    def get_extension_point(self, extension_point_id):
        """ Get the extension point associated with an id.

        Parameters
        ----------
        extension_point_id : unicode
            The fully qualified id of the extension point of interest.

        Returns
        -------
        result : ExtensionPoint or None
            The desired ExtensionPoint or None if it does not exist.

        """
        return self._registry.get_extension_point(extension_point_id)

    def get_extension_points(self):
        """ Get all of the extension points in the registry.

        Returns
        -------
        result : list
            A list of all of the extension points in the registry.

        """
        return self._registry.get_extension_points()

    def get_extension(self, extension_point_id, extension_id):
        """ Get a specific extension contributed to an extension point.

        Parameters
        ----------
        extension_point_id : unicode
            The fully qualified id of the extension point of interest.

        extension_id : unicode
            The fully qualified id of the extension.

        Returns
        -------
        result : Extension or None
            The requested Extension, or None if it does not exist.

        """
        return self._registry.get_extension(extension_point_id, extension_id)

    def get_extensions(self, extension_point_id):
        """ Get the extensions contributed to an extension point.

        Parameters
        ----------
        extension_point_id : unicode
            The fully qualified id of the extension point of interest.

        Returns
        -------
        result : list
            A list of Extensions contributed to the extension point.

        """
        return self._registry.get_extensions(extension_point_id)

    def add_listener(self, extension_point_id, listener):
        """ Add a listener to the specified extension point.

        Listeners are maintained and invoked in sorted order.

        Parameters
        ----------
        extension_point_id : unicode or None
            The fully qualified id of the extension point of interest,
            or None to install the listener for all extension points.

        listener : RegistryEventListener
            The registry listener to add to the registry.

        """
        self._registry.add_listener(extension_point_id, listener)

    def remove_listener(self, extension_point_id, listener):
        """ Remove a listener from the specified extension point.

        Parameters
        ----------
        extension_point_id : unicode or None
            The same identifier used when the listener was added.

        listener : RegistryEventListener
            The listener to remove from the registry.

        """
        self._registry.remove_listener(extension_point_id, listener)

    #--------------------------------------------------------------------------
    # Private API
    #--------------------------------------------------------------------------
    #: The registry of extension points and extensions.
    _registry = Typed(ExtensionRegistry, ())

    #: A mapping of plugin id to PluginManifest.
    _manifests = Typed(dict, ())

    #: A mapping of plugin id to Plugin instance.
    _plugins = Typed(dict, ())

    @staticmethod
    def _import_object(path):
        """ Import an object from a dot separated path.

        Parameters
        ----------
        path : unicode
            A dot separated path of the form 'pkg.module.item' which
            represents the import path to the object.

        Returns
        -------
        result : object
            The item pointed to by the path. An import error will be
            raised if the item cannot be imported.

        """
        if u'.' not in path:
            return __import__(path)
        path, item = path.rsplit(u'.', 1)
        mod = __import__(path, {}, {}, [item])
        try:
            result = getattr(mod, item)
        except AttributeError:
            raise ImportError(u'cannot import name %s' % item)
        return result

    def _create_plugin(self, manifest):
        """ Create a plugin instance for the given manifest.

        Parameters
        ----------
        manifest : PluginManifest
            The manifest which describes the plugin to create.

        Returns
        -------
        result : Plugin or None
            A new Plugin instance or None if one could not be created.

        """
        path = manifest.cls
        if not path:
            return Plugin()
        try:
            plugin_cls = self._import_object(path)
        except ImportError:
            import traceback
            msg = "failed to import plugin class '%s':\n%s"
            warnings.warn(msg % (path, traceback.format_exc()))
            return None
        plugin = plugin_cls()
        if not isinstance(plugin, Plugin):
            msg = "plugin '%s' created non-Plugin type '%s'"
            warnings.warn(msg % (path, type(plugin).__name__))
            return None
        return plugin

    def _create_extension_object(self, extension):
        """ Create the implementation object for a given extension.

        Parameters
        ----------
        extension : Extension
            The extension which contains the path to the object class.

        Returns
        -------
        result : ExtensionObject or None
            The newly created extension object, or None if one could
            not be created.

        """
        path = extension.cls
        try:
            extension_class = self._import_object(path)
        except ImportError:
            import traceback
            msg = "failed to load extension class '%s':\n%s"
            warnings.warn(msg % (path, traceback.format_exc()))
            return None
        obj = extension_class()
        if not isinstance(obj, ExtensionObject):
            msg = "extension '%s' created non-ExtensionObject type '%s'"
            warnings.warn(msg % (path, type(obj).__name__))
            return None
        return obj
