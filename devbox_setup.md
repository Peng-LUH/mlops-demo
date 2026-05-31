# Devbox Guide
## Devbox Command List

|Command|Description|
|---|---|
|`devbox version`||
|`devbox version update`||
|`devbox init`||
|`devbox add <package name>`||
|`devbox shell`||
|`devbox update`||
|`devbox list`||
|`exit`||
 

## Setup devbox
 
1. check installation
    ```bash
    devbox version
    # 0.17.2
    # If new version avaible run: devbox version update

    # if not installed, run
    curl -fsSL https://get.jetify.com/devbox | bash
    ```
    
2. Setup configuration files:
    ```bash
    devbox init

    # Created devbox.json in /home/peng-luh/__git/devops_mlops_101/mlops-demo

    # Run `devbox add <package>` to add packages, or `devbox shell` to start a dev shell.
    ```
    1. `devbox.json`: listing of all the different CLI tools that will be used.
    1. `devbox.lock`: contains the specific versions so that you will be guaranteed to get the exact version


1. create a shell containing all the dependecies defined in `devbox.json` and `devbox.lock`.
  
    ```bash
    devbox shell
    ```
    
1. to exit the shell
    ```bash
    exit
    ```

1. display all the dependencies installed within the current shell session
    ```bash
    devbox list
    ```


