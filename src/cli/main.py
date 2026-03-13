import argparse
from oecon import convert_open_ephys_recording_to_dh5
from oecon.config import load_config_from_file
from oecon.inspect import format_session_info, inspect_session
from pathlib import Path
from open_ephys.analysis.session import Session
import tkinter as tk
from tkinter import filedialog
import sys

if sys.platform == "win32":
    import winreg
import logging

logger = logging.getLogger(__name__)


def pick_open_ephys_session_via_dialog() -> Path | None:
    # Set default initialdir to ~/Documents/Open Ephys if it exists
    default_dir = Path.home() / "Documents" / "Open Ephys"

    if sys.platform == "win32":

        def get_last_dir():
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Software\IfH", 0, winreg.KEY_READ
                ) as key:
                    value, _ = winreg.QueryValueEx(key, "oe_to_dh_last_dir")
                    if value and Path(value).exists():
                        return value
            except Exception:
                return None

        def set_last_dir(path):
            try:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\IfH") as key:
                    winreg.SetValueEx(
                        key, "oe_to_dh_last_dir", 0, winreg.REG_SZ, str(path)
                    )
            except Exception:
                pass

        last_dir = get_last_dir()
        initialdir = last_dir if last_dir else None
    else:
        last_dir_file = Path.home() / ".oe_to_dh_last_dir"
        initialdir = None
        if last_dir_file.exists():
            try:
                with open(last_dir_file, "r") as f:
                    last_dir = f.read().strip()
                    if last_dir and Path(last_dir).exists():
                        initialdir = last_dir
            except Exception:
                pass

        def set_last_dir(path):
            try:
                with open(last_dir_file, "w") as f:
                    f.write(str(path))
            except Exception:
                pass

    initialdir = initialdir or default_dir

    root = tk.Tk()
    root.withdraw()
    path = filedialog.askdirectory(
        title="Select Open Ephys session folder", initialdir=initialdir
    )
    if path == "":
        return None

    set_last_dir(path)
    return Path(path)


def main():
    # oe-to-dh.exe --output-folder <output_folder> --config <config.json> --tdr <path_to_tdr_file> <oe-session>
    parser = argparse.ArgumentParser(
        description="Convert Open Ephys recordings to DH5 format."
    )

    parser.add_argument(
        "oe_session", type=str, nargs="?", help="Path to Open Ephys session folder(s)."
    )

    parser.add_argument(
        "--output-folder",
        type=str,
        default=None,
        help="Output folder for the DH5 file. Defaults to the parent folder of oe_session.",
    )

    parser.add_argument(
        "--config", type=str, help="Path to the configuration JSON file."
    )
    parser.add_argument("--tdr", type=str, help="Path to the TDR file.")
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Print a summary of the session contents and exit.",
    )

    # If oe_session is not provided, open a file dialog to pick it
    args, unknown = parser.parse_known_args()
    if args.oe_session is None:
        args.oe_session = pick_open_ephys_session_via_dialog()
    if args.oe_session is None:
        return

    # attempt to load config from path if present
    if args.config:
        config = load_config_from_file(args.config)
    else:
        config = None

    oe_session_path = Path(args.oe_session)
    if not oe_session_path.exists():
        raise FileNotFoundError(
            f"Open Ephys session folder not found: {oe_session_path}"
        )

    if args.inspect:
        print(format_session_info(inspect_session(oe_session_path)))
        return

    session = Session(str(oe_session_path))
    recording = session.recordnodes[0].recordings[0]

    if args.output_folder is None:
        output_folder = oe_session_path.parent
    else:
        output_folder = Path(args.output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    session_name = oe_session_path.name

    recording_index = 0
    for node in session.recordnodes:
        for recording in node.recordings:
            convert_open_ephys_recording_to_dh5(
                recording=recording,
                session_name=str(output_folder / session_name),
                config=config,
            )
            recording.experiment_index
            recording_index += 1


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        logger.error(f"Current config value: {locals().get('config', None)}")
