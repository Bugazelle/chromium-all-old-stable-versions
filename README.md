Chromium All Old Stable Versions
====================

> Updated at: 2019.10.22

List all possible chromium stable versions.

Hope could be the help to you. :)


## Download Links
1. [chromium.stable.json](https://raw.githubusercontent.com/Bugazelle/chromium-all-old-stable-versions/master/chromium.stable.json)
2. [chromium.stable.csv](https://raw.githubusercontent.com/Bugazelle/chromium-all-old-stable-versions/master/chromium.stable.csv)

> Warning: 
> 1. Because the omahaproxy only provide the chromium_**base**_position for the main chromium release version.

>    For example 77.x.xxxx.xx, such as [77.0.3865.75 - 681094](https://omahaproxy.appspot.com/deps.json?version=77.0.3865.90), [77.0.3865.90 - 681094](https://omahaproxy.appspot.com/deps.json?version=77.0.3865.90), they have the same position.

>    So, the chromium download urls for 77.x.xxxx.xx are the same.

>    Based on the official document, seems no better solution to fix this.
> 2. Some of certain positions don't have the chromium build. To get chromium, the position range is: [position-10, position+10]

## Download Process
1. Get Version: history.json

   Use history.json to get all the possible release chromium versions, such as **44.0.2403.157**

   https://omahaproxy.appspot.com/history.json?channel=stable&os=linux

   > OS: Linux, Mac, Win

2. Get Position: deps.json

   Use deps.json to get the chromium_base_position from a provided chromium version: **44.0.2403.157 -> 330231**

   https://omahaproxy.appspot.com/deps.json?version=44.0.2403.157

3. Get Download Url: googleapis

   Prepare Download Urls. If 404 error, try to use position [position-10, position+10] to download again.
   For example: **330231 -> 330234**

   https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F330234%2Fchrome-linux.zip?alt=media

   ![DownloadProcess](src/DownloadProcess.png)

## Build Process
Consider behavior takes time, use DockerHub to get chromium url.

And then push the chromium zips back to repo.

## Chrome (Not Chromium) Old/History Versions

1. Linux NPM Packages: [http://orion.lcg.ufrj.br/RPMS/myrpms/google/](http://orion.lcg.ufrj.br/RPMS/myrpms/google/)

2. Linux Deb, Mac, Windows Packages: [https://www.slimjet.com/chrome/google-chrome-old-version.php](https://www.slimjet.com/chrome/google-chrome-old-version.php)

