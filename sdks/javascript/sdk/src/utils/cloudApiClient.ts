import { CLOUD_API_MANAGE_URL, CLOUD_QUERY_URL } from "../constants";
import type { RequestBody } from "../models";

export class CloudApiClient {
  private baseUrl: string;
  private queryUrl: string;

  constructor(
    private projectId: string,
    private projectKey: string,
    baseUrl: string = CLOUD_API_MANAGE_URL,
    queryUrl: string = CLOUD_QUERY_URL,
  ) {
    this.baseUrl = baseUrl;
    this.queryUrl = queryUrl;
  }

  async makeRequest<T, U extends Partial<RequestBody> = Partial<RequestBody>>(
    action: string,
    additionalData?: Omit<U, "action" | "projectId">,
  ): Promise<T> {
    const requestBody: RequestBody & Omit<U, "action" | "projectId"> = {
      action,
      projectId: this.projectId,
      ...additionalData,
    } as RequestBody & Omit<U, "action" | "projectId">;

    try {
      const response = await fetch(this.baseUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Project-Key": this.projectKey,
        },
        body: JSON.stringify(requestBody),
        signal: AbortSignal.timeout(600_000),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data as T;
    } catch (error) {
      throw new Error(
        `Cloud API request failed: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }
  }

  async makeQueryRequest<T>(
    indexName: string,
    query: string,
    topK: number = 10,
    queryEmbedding?: number[],
  ): Promise<T> {
    const requestBody: Record<string, any> = {
      query,
      indexName,
      projectId: this.projectId,
      projectKey: this.projectKey,
      topK,
    };

    if (queryEmbedding) {
      requestBody.queryEmbedding = queryEmbedding;
    }

    try {
      const response = await fetch(this.queryUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
        signal: AbortSignal.timeout(60_000),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return (await response.json()) as T;
    } catch (error) {
      throw new Error(
        `Cloud query request failed: ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }
  }
}
