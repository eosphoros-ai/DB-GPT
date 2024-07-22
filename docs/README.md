# DB-GPT documentation 

## Quick Start

### Install dependencies 
- Clone current project firstly!
- Install docusaurus dependencies, generate node_modules folder.

```
sudo yarn install
```

### launch
``` 
yarn start
```

The default service starts on port `3000`, visit `localhost:3000`

## Deploy Multi-Version Documentation

We can deploy multiple versions of the documentation by docker.

### Build Docker Image

Firstly, build the docker image in `DB-GPT` project root directory.

```bash
# Use the default NPM_REGISTRY=https://registry.npmjs.org
# Use https://www.npmmirror.com/
NPM_REGISTRY=https://registry.npmmirror.com
docker build -f docs/Dockerfile-deploy \
-t eosphorosai/dbgpt-docs \
--build-arg NPM_REGISTRY=$NPM_REGISTRY \
--build-arg CI=false \
--build-arg NUM_VERSION=2 .
```

### Run Docker Container

Run the docker container with the following command:
```bash
docker run -it --rm -p 8089:8089 \
--name my-dbgpt-docs \
-v $(pwd)/docs/nginx/nginx-docs.conf:/etc/nginx/nginx.conf \
eosphorosai/dbgpt-docs
```

Open the browser and visit `localhost:8089` to see the documentation.