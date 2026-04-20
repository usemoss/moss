import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

export default [
  js.configs.recommended,
  { 
    files: ["**/*.{js,mjs,cjs,ts}"], 
    languageOptions: { globals: globals.node } 
  },
  ...tseslint.configs.recommended,
];