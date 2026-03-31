export interface MossSearchOptions {
  /** Moss project ID */
  projectId: string
  /** Moss project API key */
  projectKey: string
  /** Name of the Moss index to use */
  indexName: string
  /** Number of results to return. Default: 10 */
  topK?: number
  /** Placeholder text in the search input. Default: 'Search docs...' */
  placeholder?: string
  /** Text shown on the nav search button. Default: 'Search' */
  buttonText?: string
}
