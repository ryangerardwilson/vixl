package cli

const HelpText = `vixl
terminal CSV spreadsheet editor

global actions:
  vixl help
    show this help
  vixl version
    print the installed version
  vixl upgrade
    upgrade to the latest release
  vixl config
    open the config in $VISUAL/$EDITOR

features:
  open the spreadsheet editor on a new sheet or an existing path
  # vixl open [path]
  vixl open
  vixl open data.csv

  edit command history, clipboard integration, and other local settings
  # vixl config
  vixl config
`
