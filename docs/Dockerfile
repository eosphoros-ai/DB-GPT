FROM node:lts

WORKDIR /app
COPY . /app

RUN yarn install

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "serve"]
