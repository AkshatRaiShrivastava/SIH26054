FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Expose Vite port
EXPOSE 5173

# Start Vite with host binding
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
