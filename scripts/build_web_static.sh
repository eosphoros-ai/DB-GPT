#!/bin/bash

cd ../web

npm install
npm run build

rm -rf ../dbgpt/app/static/*

cp -R ../web/out/* ../dbgpt/app/static