/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BASEMAP_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
