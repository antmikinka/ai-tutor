; Custom NSIS hooks for the electron-builder installer.
;
; electron-builder includes this file into its own script and calls the
; ``customInstall`` / ``customUnInstall`` macros. Only those macros belong
; here: Sections, ``Function`` definitions and a second ``Section "Uninstall"``
; would collide with the generated script.
;
; The Python backend is shipped as source under $INSTDIR\resources\backend and
; needs a Python 3.10+ interpreter at run time (see README). We do not try to
; pip-install anything at install time: Program Files is read-only for users
; and there is no bundled interpreter to run pip with.

!macro customInstall
  ; Where the app keeps models/logs/data (matches app.getPath('userData')).
  CreateDirectory "$APPDATA\${PRODUCT_FILENAME}\models"
  CreateDirectory "$APPDATA\${PRODUCT_FILENAME}\logs"
  CreateDirectory "$APPDATA\${PRODUCT_FILENAME}\data"

  ; Tell the user up-front if Python is missing instead of failing silently at launch.
  nsExec::ExecToStack 'python --version'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONINFORMATION|MB_OK "AI Math Tutor needs Python 3.10 or newer on PATH to run its local backend.$\r$\n$\r$\nInstall it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run:$\r$\n  pip install -r $\"$INSTDIR\resources\backend\requirements.txt$\""
  ${EndIf}
!macroend

!macro customUnInstall
  ; Program files are removed by the generated uninstaller. Downloaded models
  ; can be tens of gigabytes, so ask before deleting user data.
  MessageBox MB_YESNO|MB_ICONQUESTION "Also delete downloaded AI models, logs and settings in$\r$\n$APPDATA\${PRODUCT_FILENAME}?" IDNO skipUserData
    RMDir /r "$APPDATA\${PRODUCT_FILENAME}"
  skipUserData:
!macroend
