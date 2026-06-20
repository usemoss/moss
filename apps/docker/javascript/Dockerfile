FROM node:20-trixie-slim

WORKDIR /app

COPY package.json .
RUN npm install

COPY main.ts .

CMD ["npx", "tsx", "main.ts"]
