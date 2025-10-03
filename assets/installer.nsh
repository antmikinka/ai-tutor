; Custom NSIS script for AI Math Tutor installer

!macro preInit
    SetRegView 64
    WriteRegExpandStr HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation "$INSTDIR"
    WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation "$INSTDIR"
    SetRegView 32
    WriteRegExpandStr HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation "$INSTDIR"
    WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation "$INSTDIR"
    WriteRegExpandStr HKLM "${INSTALL_REGISTRY_KEY}" UninstallString "$INSTDIR\uninstall.exe"
    WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" UninstallString "$INSTDIR\uninstall.exe"
!macroend

Section "Application Start Menu Shortcut"
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXECUTABLE_FILENAME}"
    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall ${PRODUCT_NAME}.lnk" "$INSTDIR\uninstall.exe"
SectionEnd

Section "Desktop Shortcut"
    CreateShortcut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXECUTABLE_FILENAME}"
SectionEnd

Section "Add to Path"
    Push "$INSTDIR\backend"
    Call AddToPath
SectionEnd

Section "Install Python Dependencies"
    ; This section would install Python dependencies
    ; In production, you might bundle Python with the installer
    ExecWait '"$INSTDIR\backend\python.exe" -m pip install -r "$INSTDIR\backend\requirements.txt"'
SectionEnd

Section "Configure Model Cache"
    ; Create model cache directory
    CreateDirectory "$APPDATA\AI Math Tutor\models\cache"
    WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" ModelCacheDir "$APPDATA\AI Math Tutor\models\cache"
SectionEnd

Section "Register File Associations"
    ; Register file associations for mathematical files
    WriteRegExpandStr HKCR ".math" "" "AI.MathTutor.File"
    WriteRegExpandStr HKCR "AI.MathTutor.File" "" "Mathematical Problem File"
    WriteRegExpandStr HKCR "AI.MathTutor.File\DefaultIcon" "" "$INSTDIR\${PRODUCT_EXECUTABLE_FILENAME},0"
    WriteRegExpandStr HKCR "AI.MathTutor.File\shell\open\command" "" '"$INSTDIR\${PRODUCT_EXECUTABLE_FILENAME}" "%1"'
SectionEnd

Section "Uninstall"
    ; Remove registry keys
    DeleteRegKey HKLM "${INSTALL_REGISTRY_KEY}"
    DeleteRegKey HKCU "${INSTALL_REGISTRY_KEY}"
    DeleteRegKey HKCR ".math"
    DeleteRegKey HKCR "AI.MathTutor.File"

    ; Remove shortcuts
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall ${PRODUCT_NAME}.lnk"
    RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
    Delete "$DESKTOP\${PRODUCT_NAME}.lnk"

    ; Remove application files
    RMDir /r "$INSTDIR"

    ; Remove app data
    RMDir /r "$APPDATA\AI Math Tutor"

    ; Remove from PATH
    Push "$INSTDIR\backend"
    Call un.RemoveFromPath
SectionEnd