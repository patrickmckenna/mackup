"""Package used to manage the .mackup.cfg config file."""

import logging
import os.path
import pathlib

from .constants import (
    CUSTOM_APPS_DIR,
    MACKUP_BACKUP_PATH,
    MACKUP_CONFIG_FILE,
    ENGINE_DROPBOX,
    ENGINE_GDRIVE,
    ENGINE_COPY,
    ENGINE_ICLOUD,
    ENGINE_FS,
)

from .utils import (
    error,
    get_dropbox_folder_location,
    get_copy_folder_location,
    get_google_drive_folder_location,
    get_icloud_folder_location,
)

try:
    import configparser
except ImportError:
    import ConfigParser as configparser



logger = logging.getLogger(__name__)


class Config(object):

    """The Mackup Config class."""

    def __init__(self, config_path=None):
        """
        Create a Config instance.

        Args:
            config_path (str): Optional path to a mackup config file.
        """

        # Initialize the parser
        self._parser = self._setup_parser(config_path)

        # Do we have an old config file ?
        self._warn_on_old_config()

        # Get the storage engine
        self._engine = self._parse_engine()

        # Get the path where the Mackup folder is
        self._path = self._parse_path()

        # Get the directory replacing 'Mackup', if any
        self._directory = self._parse_directory()

        # Get the list of apps to ignore
        self._apps_to_ignore = self._parse_apps_to_ignore()

        # Get the list of apps to allow
        self._apps_to_sync = self._parse_apps_to_sync()

    @property
    def engine(self):
        """
        The engine used by the storage.

        ENGINE_DROPBOX, ENGINE_GDRIVE, ENGINE_COPY, ENGINE_ICLOUD or ENGINE_FS.

        Returns:
            str
        """
        return str(self._engine)

    @property
    def path(self):
        """
        Path to the Mackup configuration files.

        The path to the directory where Mackup is gonna create and store his
        directory.

        Returns:
            str
        """
        return str(self._path)

    @property
    def directory(self):
        """
        The name of the Mackup directory, named Mackup by default.

        Returns:
            str
        """
        return str(self._directory)

    @property
    def fullpath(self):
        """
        Full path to the Mackup configuration files.

        The full path to the directory when Mackup is storing the configuration
        files.

        Returns:
            str
        """
        return str(os.path.join(self.path, self.directory))

    @property
    def apps_to_ignore(self):
        """
        Get the list of applications ignored in the config file.

        Returns:
            set. Set of application names to ignore, lowercase
        """
        return set(self._apps_to_ignore)

    @property
    def apps_to_sync(self):
        """
        Get the list of applications allowed in the config file.

        Returns:
            set. Set of application names to allow, lowercase
        """
        return set(self._apps_to_sync)

    @classmethod
    def _resolve_config_path(cls, filename=None):
        """
        Resolve the optional, user-supplied path to a Mackup config file. If
        none supplied, defaults to looking for MACKUP_CONFIG_FILE in the user's
        home directory.

        Returns:
            str, or None if filename doesn't exist
        """
        file_exists = lambda p: os.path.isfile(p)

        if filename is None:
            # use $HOME, instead of pathlib.Path.home, to preserve existing behavior
            # (some unit tests rely on monkeypatching that value)
            path = os.path.join(os.environ["HOME"], MACKUP_CONFIG_FILE)
            if file_exists(path):
                return os.path.abspath(path)
            else:
                logger.warning(f"Default config file {path} not found, and no alternative filename given.")
                return None

        possible_paths = [
            os.path.expanduser(filename),
            os.path.join(os.environ["HOME"], filename),
            os.path.join(os.getcwd(), filename)
        ]
        path = next(filter(file_exists, possible_paths), None)
        if path:
            return os.path.abspath(path)
        else:
            logger.warning(f"Config file {filename} not found! Tried paths: {possible_paths}")
            return None

    def _setup_parser(self, config_path=None):
        """
        Configure the ConfigParser instance the way we want it.

        Args:
            config_path (str): Optional path to a mackup config file.
        Returns:
            SafeConfigParser
        """
        parser = configparser.SafeConfigParser(allow_no_value=True)
        # call will return None if config_path doesn't exist
        path = self._resolve_config_path(config_path) or ""
        parser.read(path)

        return parser

    def _warn_on_old_config(self):
        """Warn the user if an old config format is detected."""
        # Is an old setion is in the config file ?
        old_sections = ["Allowed Applications", "Ignored Applications"]
        for old_section in old_sections:
            if self._parser.has_section(old_section):
                error(
                    "Old config file detected. Aborting.\n"
                    "\n"
                    "An old section (e.g. [Allowed Applications]"
                    " or [Ignored Applications] has been detected"
                    " in your {} file.\n"
                    "I'd rather do nothing than do something you"
                    " do not want me to do.\n"
                    "\n"
                    "Please read the up to date documentation on"
                    " <https://github.com/lra/mackup> and migrate"
                    " your configuration file.".format(MACKUP_CONFIG_FILE)
                )

    def _parse_engine(self):
        """
        Parse the storage engine in the config.

        Returns:
            str
        """
        if self._parser.has_option("storage", "engine"):
            engine = str(self._parser.get("storage", "engine"))
        else:
            engine = ENGINE_DROPBOX

        assert isinstance(engine, str)

        if engine not in [
            ENGINE_DROPBOX,
            ENGINE_GDRIVE,
            ENGINE_COPY,
            ENGINE_ICLOUD,
            ENGINE_FS,
        ]:
            raise ConfigError("Unknown storage engine: {}".format(engine))

        return str(engine)

    def _parse_path(self):
        """
        Parse the storage path in the config.

        Returns:
            str
        """
        if self.engine == ENGINE_DROPBOX:
            path = get_dropbox_folder_location()
        elif self.engine == ENGINE_GDRIVE:
            path = get_google_drive_folder_location()
        elif self.engine == ENGINE_COPY:
            path = get_copy_folder_location()
        elif self.engine == ENGINE_ICLOUD:
            path = get_icloud_folder_location()
        elif self.engine == ENGINE_FS:
            if self._parser.has_option("storage", "path"):
                cfg_path = self._parser.get("storage", "path")
                path = os.path.join(os.environ["HOME"], cfg_path)
            else:
                raise ConfigError(
                    "The required 'path' can't be found while"
                    " the 'file_system' engine is used."
                )

        return str(path)

    def _parse_directory(self):
        """
        Parse the storage directory in the config.

        Returns:
            str
        """
        if self._parser.has_option("storage", "directory"):
            directory = self._parser.get("storage", "directory")
            # Don't allow CUSTOM_APPS_DIR as a storage directory
            if directory == CUSTOM_APPS_DIR:
                raise ConfigError(
                    "{} cannot be used as a storage directory.".format(CUSTOM_APPS_DIR)
                )
        else:
            directory = MACKUP_BACKUP_PATH

        return str(directory)

    def _parse_apps_to_ignore(self):
        """
        Parse the applications to ignore in the config.

        Returns:
            set
        """
        # We ignore nothing by default
        apps_to_ignore = set()

        # Is the "[applications_to_ignore]" in the cfg file ?
        section_title = "applications_to_ignore"
        if self._parser.has_section(section_title):
            apps_to_ignore = set(self._parser.options(section_title))

        return apps_to_ignore

    def _parse_apps_to_sync(self):
        """
        Parse the applications to backup in the config.

        Returns:
            set
        """
        # We allow nothing by default
        apps_to_sync = set()

        # Is the "[applications_to_sync]" section in the cfg file ?
        section_title = "applications_to_sync"
        if self._parser.has_section(section_title):
            apps_to_sync = set(self._parser.options(section_title))

        return apps_to_sync


class ConfigError(Exception):

    """Exception used for handle errors in the configuration."""

    pass
