import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Dashboard effects intentionally initiate async API synchronization.
      // The React 19 rule reports the loading-state update inside those
      // functions even though the effect itself does not derive local state.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
