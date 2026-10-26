# Node.js and the Playwright browsers in one image; the tag matches @playwright/test.
FROM mcr.microsoft.com/playwright:v1.64.1-noble

WORKDIR /app

# node_modules lives in a named volume; Docker fills it from this layer on first use.
COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit

CMD ["npm", "run", "dev"]
