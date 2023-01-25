## Installation fow Windows

1. execute the `script-install.bat`
    - This will install the python and the libraries required
2. edit the `script-cron.bat`
    - Add the branch (--b) option at the end of the line where flask command execution (eg: `call venv\Scripts\flask scheduled --b=1234`)


## File description
* script-install.bat - install python and required libraries
* script-cron.bat - syncronize product items
* script-serve.bat - serve as web app


## To make the project availabe on browser
1. Check the `script-serve.bat` and edit depending on the port you want it to run (default is 8080)
2. Execute the `script-serve.bat`
3. Do not close the window it opened - for development purposes so you can see the access and error logs