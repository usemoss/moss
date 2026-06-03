# Moss Next.js Demo

A modern semantic search interface built with Next.js 16, React, and the Moss Web SDK.

This demo showcases how to use `@moss-dev/moss-web` to interact with Moss from a web application.

## 🚀 Features

- **Sub-10ms Retrieval**: Experience Moss's industry-leading speed in a browser.
- **Client-side Search**: Build, load, query and delete a Moss index directly in the browser.
- **Glassmorphism UI**: A sleek, responsive dark-mode interface.
- **Real-time Stats**: View retrieval time and match confidence scores.

## ⚙️ Setup

1. **Install Dependencies**:

   ```bash
   npm install
   ```

2. **Configure Credentials**:
   Get your credentials from the [Moss Portal](https://portal.usemoss.dev), then enter your `MOSS_PROJECT_ID` and `MOSS_PROJECT_KEY` in the app UI after it starts.

3. **Run Development Server**:
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

## 📁 Structure

- `app/page.tsx`: The main UI component (Client Side).
- `app/page.test.tsx`: UI behavior tests.
- `app/globals.css`: Premium styling and glassmorphism definitions.

## 🛠️ Integration Guide

To add Moss to your own Next.js app:

1. Install the SDK: `npm install @moss-dev/moss-web`
2. Instantiate `MossClient` in a client component.
3. Call it from your React components to create, load, and query indexes.
