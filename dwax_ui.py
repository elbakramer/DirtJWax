from pathlib import Path

from pygame_gui.windows.ui_file_dialog import UIFileDialog
from pygame_gui.elements.ui_drop_down_menu import UIDropDownMenu


class FilteredUIFileDialog(UIFileDialog):
    def __init__(self, *args, **kwargs):
        self._predicate = kwargs.pop("predicate")

        if self._predicate is None:
            self._predicate = lambda item: True

        super().__init__(*args, **kwargs)

    def update_current_file_list(self):
        try:
            directories_on_path = [
                f.name
                for f in Path(self.current_directory_path).iterdir()
                if not f.is_file()
            ]
            directories_on_path = sorted(directories_on_path, key=str.casefold)
            directories_on_path_tuples = [
                (f, "#directory_list_item") for f in directories_on_path
            ]

            files_on_path = [
                f.name
                for f in Path(self.current_directory_path).iterdir()
                if f.is_file() and self._predicate(f)
            ]
            files_on_path = sorted(files_on_path, key=str.casefold)
            files_on_path_tuples = [(f, "#file_list_item") for f in files_on_path]

            self.current_file_list = directories_on_path_tuples + files_on_path_tuples
        except (PermissionError, FileNotFoundError):
            self.current_directory_path = self.last_valid_directory_path
            self.update_current_file_list()
        else:
            self.last_valid_directory_path = self.current_directory_path


class UpdateableUIDropDownMenu(UIDropDownMenu):
    def set_selected_option(self, selected_option):
        self.selected_option = selected_option

        closed_menu = self.menu_states["closed"]
        expanded_menu = self.menu_states["expanded"]

        closed_menu.selected_option = selected_option
        expanded_menu.selected_option = selected_option

        if closed_menu.selected_option_button:
            closed_menu.selected_option_button.set_text(selected_option)
        if expanded_menu.selected_option_button:
            expanded_menu.selected_option_button.set_text(selected_option)
