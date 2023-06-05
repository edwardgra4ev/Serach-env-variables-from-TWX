from PySide6 import QtWidgets
from PySide6.QtWidgets import QFileDialog, QWidget, QListWidgetItem, QTreeWidgetItem
from PySide6.QtCore import Slot, Signal, QThread
from operator import is_not
from functools import partial
import fileinput
import zipfile
import ui
from modal import Ui_Dialog
import os
import sys
import xml.etree.ElementTree as ET

from qt_material import apply_stylesheet


class ExampleApp(QtWidgets.QMainWindow, ui.Ui_MainWindow):
    speak = Signal((list,))

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.load_setting()
        self.twx_file_path = None
        self.folder_path = None
        self.env_variables = []
        self.custom_env_variables = []
        self.dialog = None
        self.thread = None

        self.pushButton.clicked.connect(self.show_file_dialog)
        self.pushButton_3.clicked.connect(self.search_env_variables)
        self.pushButton_4.clicked.connect(self.show_add_variables_dialog)
        self.pushButton_2.clicked.connect(self.start_search_thread)
        self.pushButton_5.clicked.connect(self.treeWidget.clear)
        self.speak[list].connect(self.set_custom_variables)

    def load_setting(self) -> None:
        self.comboBox.hide()
        self.pushButton_2.hide()
        self.pushButton_3.hide()
        self.pushButton_4.hide()
        self.progressBar.hide()
        self.treeWidget.clear()
        self.treeWidget.setHeaderLabels(["Результат поиска"])
        # При тайкой настройке он плавающий
        self.progressBar.setValue(0)
        self.progressBar.setMaximum(0)


    @Slot(list)
    def set_custom_variables(self, variables: list[str]) -> None:
        self.custom_env_variables = variables
        self.env_variables.extend(self.custom_env_variables)
        self.env_variables = list(set(self.env_variables))
        self.update_combo_box()
    

    def show_add_variables_dialog(self) -> None:
        self.dialog = Dialog(self, self.custom_env_variables)
        self.dialog.show()


    def update_combo_box(self) -> None:
        self.comboBox.clear()
        self.comboBox.addItems(self.env_variables)
        self.comboBox.show()


    def search_env_variables(self) -> None:
        self.progressBar.show()
        files = self.get_all_files_by_path()
        file = self.search_for_files_with_env_variables(files)
        self.env_variables = self.get_list_of_variables_from_file(file)
        self.update_combo_box()
        self.pushButton_4.show()
        self.pushButton_2.show()
        self.progressBar.hide()
        

    def show_file_dialog(self) -> None:
        self.twx_file_path, _ = QFileDialog.getOpenFileName(self, "Выберите twx файл", ".", "TWX files (*.twx)")
        self.folder_path = self.unpacking()
        self.lineEdit.setText(self.twx_file_path)
        self.lineEdit_2.setText(self.folder_path)
        self.pushButton_3.show()
    

    def unpacking(self) -> str:
        folder = "./TWX"
        name =  folder + "/" + self.twx_file_path.split('/')[-1].replace(".twx", "")
        if os.path.isdir(name):
            return name
        with zipfile.ZipFile(self.twx_file_path, 'r') as zip_file: 
            for file in zip_file.namelist():
                if "objects" in file:
                    zip_file.extract(file, folder)
        os.rename("./TWX/objects", name)
        return name
        

    def get_all_files_by_path(self) -> tuple[str]:
        return tuple(os.path.join(self.folder_path, file) for _, _, filenames in os.walk(self.folder_path) for file in filenames)


    def search_for_files_with_env_variables(self, files: tuple[str]):
        with fileinput.input(files=files) as file:
            for line in file:
                if 'environmentVariableSet' in line:
                    return file.filename()
                
                
    def get_list_of_variables_from_file(self, path: str) -> tuple[str]:
        root = ET.parse(path).getroot()
        result = list(
            filter(
                partial(is_not, None), 
                [envVar.attrib.get('name') for envVar in root[0]]
            )
        )
        return result


    def start_search_thread(self) -> None:
        if self.comboBox.currentText() =="":
            return
        self.thread =  MyThread(self)
        self.thread.run()
    

    def remove_item_from_tree_by_name(self, name: str) -> None:
        for index in range(self.treeWidget.topLevelItemCount()):
            item = self.treeWidget.topLevelItem(index)
            if item.text(0) == name:
                self.treeWidget.takeTopLevelItem(index)
                return
                

    def find_files_in_with_the_variables_used(self, variable_name, files: tuple) -> tuple[str]:
        result = []
        variable = f"tw.env.{variable_name}"
        with fileinput.input(files=files) as file:
            for line in file:
                if variable in line:
                    result.append(file.filename())
                    file.nextfile()
        return tuple(result)

    def setEnabledWidgets(self, flag: bool) -> None:
        self.pushButton.setEnabled(flag)
        self.pushButton_2.setEnabled(flag)
        self.pushButton_3.setEnabled(flag)
        self.pushButton_4.setEnabled(flag)
        self.comboBox.setEnabled(flag)

    

class Dialog(QWidget, Ui_Dialog):
    def __init__(self, mainWindow, variables,*args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        self.setupUi(self)
        self.mainWindow = mainWindow
        self.variables = variables
        if len(self.variables) > 0:
            for i in self.variables:
                self.update(i) 
        self.pushButton_3.clicked.connect(self.add)
        self.pushButton_2.clicked.connect(self.close)
        self.pushButton.clicked.connect(self.setVariables)
    

    def add(self) -> None:
        if self.lineEdit.text() != "":
            self.variables.append(self.lineEdit.text())
            self.update(self.lineEdit.text())
            self.lineEdit.setText("")

    def update(self, text) -> None:
        item = QListWidgetItem()
        item.setText(text)
        self.listWidget.addItem(item)

    def setVariables(self) -> None:
        self.mainWindow.speak.emit(self.variables)
        self.close()


class MyThread(QThread):
    def __init__(self, main, parent = None):
        QThread.__init__(self, parent)
        self.exiting = False
        self.main = main

    def run(self):
        self.main.setEnabledWidgets(False)
        self.main.progressBar.show()
        files = self.main.get_all_files_by_path()
        files = self.main.find_files_in_with_the_variables_used(self.main.comboBox.currentText(),files)
        if files != []:
            if item := self.searching_for_data_by_variable(files, self.main.comboBox.currentText()):
                self.main.remove_item_from_tree_by_name(item.get("VariableName"))
                tree_widget_item1 = QTreeWidgetItem([item.get("VariableName")])
                
                for artifact in item.get("Result"):
                    name = artifact.get("ArtefactName")
                    tree_widget_item2 = QTreeWidgetItem([name])
                    if len(name.split("-")) == 5:
                        tree_widget_item2.setToolTip(0, "Это вложенный процесс/подпроцесс.\nИмя родителя где он используется можно найти но очень затратно!")
                    for child_artifacts in artifact.get("ChildArtifacts"):
                        tree_widget_item2.addChild(QTreeWidgetItem([child_artifacts]))
                    tree_widget_item1.addChild(tree_widget_item2)
                self.main.treeWidget.addTopLevelItem(tree_widget_item1)
        
        self.main.setEnabledWidgets(True)
        self.main.progressBar.hide()
    
    def searching_for_data_by_variable(self, files: tuple, variable_name):
        variable = f"tw.env.{variable_name}"
        result = {"VariableName": variable}
        list_result = []
        for file in files:
            # Получаем объект XML Файла
            root = ET.parse(file).getroot()
            artefact_name = root[0].attrib.get('name')
            # Если имя артефакта UID берем ID
            if len(artefact_name.split('-')) == 5:
                    artefact_name = root[0].attrib.get('id')
            data = {"ArtefactName": artefact_name}
            data_list = []
            # Получаем все вложенные артефакты
            child_items = tuple(
                {elem for elem in root.iter() if elem.tag == 'item' or elem.tag == 'flowObject'})
            # Находим вложенные артефакты в которых есть нужная переменная
            for item in child_items:
                for i in item.iter():
                    if i.text and variable_name in i.text:
                        # Получаем имя вложенного артефакта
                        data_list.append([element.text for element in item.iter()
                                        if element.tag == "name"][0])
            data["ChildArtifacts"] = data_list
            list_result.append(data)
        result["Result"] = list_result
        return result

            
def main():
    app = QtWidgets.QApplication(sys.argv)  # Новый экземпляр QApplication
    window = ExampleApp()  # Создаём объект класса ExampleApp
    apply_stylesheet(app, theme='dark_teal.xml')
    window.show()  # Показываем окно
    app.exec_()  # и запускаем приложение


if __name__ == '__main__':  # Если мы запускаем файл напрямую, а не импортируем
    main()  # то запускаем функцию main()