import * as MossCore from "@moss-dev/moss-core";

const rustCore = MossCore as unknown as {
  MODEL_DOWNLOAD_URL: string;
  SDK_VERSION_NUMBER: string;
  CLOUD_API_MANAGE_URL: string;
};

export const MODEL_DOWNLOAD_URL = rustCore.MODEL_DOWNLOAD_URL;

/** Base manage URL — sourced from the Rust core constant. */
export const CLOUD_API_MANAGE_URL = rustCore.CLOUD_API_MANAGE_URL;

/** Query URL — derived from the manage URL. */
export const CLOUD_QUERY_URL =
  CLOUD_API_MANAGE_URL.replace("/v1/manage", "/query");

export const SDK_VERSION_NUMBER = rustCore.SDK_VERSION_NUMBER;
