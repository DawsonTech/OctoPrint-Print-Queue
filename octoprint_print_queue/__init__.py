# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from pprint import pprint
from octoprint.server import printer, NO_CONTENT
import flask
import os

class PrintQueuePlugin(octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.EventHandlerPlugin):

    printqueue = 0

# StartupPlugin
    def on_after_startup(self):
        self._materials_file_path = os.path.join(self.get_plugin_data_folder(), "print_queue.yaml")
        self._materials_dict = None
        self._getMaterialsDict()

# BluePrintPlugin (api requests)
    @octoprint.plugin.BlueprintPlugin.route("/scriptget", methods=["GET"])
    def getMaterialsData(self):
        materials = self._getMaterialsDict()
        return flask.jsonify(materials)

    @octoprint.plugin.BlueprintPlugin.route("/scriptset", methods=["POST"])
    def setMaterialsData(self):
        materials = self._getMaterialsDict()
        materials["bed_clear_script"] = flask.request.values["bed_clear_script"];
        self._writeMaterialsFile(materials)
        return flask.make_response("POST successful", 200)

    @octoprint.plugin.BlueprintPlugin.route("/runtest", methods=["POST"])
    def runTest(self):
        self._logger.info("MSL: successfully called test method")
        # octoprint.printer.start_print()
        self._logger.info("MSL: octoprint" + ', '.join(dir(octoprint)))
        self._logger.info("MSL: octoprint.printer " + ', '.join(dir(octoprint.printer)))
        self._logger.info("MSL: self " + ', '.join(dir(self)))
        # self._printer.start_print()
        return flask.make_response("POST successful", 200)

    @octoprint.plugin.BlueprintPlugin.route("/printcontinuously", methods=["POST"])
    def printContinuously(self):
        self._logger.info("MSL: successfully called print continuously method")
        self.printqueue = int(flask.request.values["amount"])
        self._logger.info("MSL: printing copies: " + str(self.printqueue))
        if self.printqueue > 0:
            self._printer.start_print()
        return flask.make_response("POST successful", 200)

# SettingsPlugin
    def get_settings_defaults(self):
        return dict(bed_temp="50",
            print_temp="200")

# TemplatePlugin
    def get_template_vars(self):
        return dict(
            bed_temp=self._settings.get(["bed_temp"]),
            print_temp=self._settings.get(["print_temp"]))

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False),
        ]

# AssetPlugin
    def get_assets(self):
        return dict(
            js=["js/print_queue.js"]
    )

# Data Persistence
    def _writeMaterialsFile(self, materials):
        try:
            import yaml
            from octoprint.util import atomic_write
            with atomic_write(self._materials_file_path) as f:
                yaml.safe_dump(materials, stream=f, default_flow_style=False, indent="  ", allow_unicode=True)
        except:
            self._logger.info("MSL: error writing materials file")
        else:
            self._materials_dict = materials

    def _getMaterialsDict(self):
        result_dict = None
        if os.path.exists(self._materials_file_path):
            with open(self._materials_file_path, "r") as f:
                try:
                    import yaml
                    result_dict = yaml.safe_load(f)
                except:
                    self._logger.info("MSL: error loading materials file")
                else:
                    if not result_dict:
                        result_dict = dict()
        else: 
            result_dict = dict()
        self._materials_dict = result_dict
        return result_dict

    def print_completion_script(self, comm, script_type, script_name, *args, **kwargs):
        if script_type == "gcode" and script_name == "afterPrintDone" and self.printqueue > 0:
            prefix = self._materials_dict["bed_clear_script"]
            postfix = None
            return prefix, postfix
        else:
            return None

    # Event Handling
    def on_event(self, event, payload):
        if event == "PrintDone":
            if self.printqueue > 0:
                self.printqueue -= 1
                if self.printqueue > 0: self._printer.start_print()
        return

__plugin_name__ = "Print Queue"
def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PrintQueuePlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.scripts": __plugin_implementation__.print_completion_script,
    }