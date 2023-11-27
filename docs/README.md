# DB-GPT Website

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

## Docker development 

```commandline
docker build -t dbgptweb .
docker run --restart=unless-stopped -d -p 3000:3000 dbgptweb
```
