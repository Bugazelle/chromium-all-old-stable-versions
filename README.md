Chromium All Old Stable Versions
====================

List all possible chromium stable versions here.

Hope could be the help to you. :)

> Note: Some of certain positions don't have the chromium build. To get chromium, the position range is: [position-10, position+10]

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
Consider downloading behavior takes time, use DockerHub to download the chromium.

And then push the chromium zips back to repo.

If you are still interesting about the **HUGE** docker image, pull it! ;)

```
docker pull bugazelle/chromium-all-old-stable-versions
```
