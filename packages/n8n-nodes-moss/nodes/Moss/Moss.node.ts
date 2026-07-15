import type {
	IDataObject,
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';
import { NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';

import {
	addDocs,
	createIndex,
	deleteDocs,
	deleteIndex,
	getDocs,
	getIndex,
	getJobStatus,
	listIndexes,
	parseDocuments,
	parseStringList,
	queryIndex,
	type MossCredentials,
} from './GenericFunctions';

async function getMossCredentials(this: IExecuteFunctions): Promise<MossCredentials> {
	const credentials = await this.getCredentials('mossApi');
	const projectId = credentials.projectId as string;
	const projectKey = credentials.projectKey as string;

	if (!projectId || !projectKey) {
		throw new NodeOperationError(this.getNode(), 'Moss Project ID and Project Key are required');
	}

	return { projectId, projectKey };
}

const waitProperties = [
	{
		displayName: 'Wait for Completion',
		name: 'waitForCompletion',
		type: 'boolean' as const,
		default: true,
		description:
			'Whether to poll until the async Moss job finishes. Disable to return the jobId immediately and poll with Get Job Status.',
		displayOptions: {
			show: {
				operation: ['createIndex', 'addDocs', 'deleteDocs'],
			},
		},
	},
	{
		displayName: 'Max Wait (Seconds)',
		name: 'maxWaitSeconds',
		type: 'number' as const,
		typeOptions: {
			minValue: 5,
			maxValue: 1800,
		},
		default: 300,
		description: 'Maximum seconds to wait when Wait for Completion is enabled',
		displayOptions: {
			show: {
				operation: ['createIndex', 'addDocs', 'deleteDocs'],
				waitForCompletion: [true],
			},
		},
	},
];

export class Moss implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Moss',
		name: 'moss',
		icon: { light: 'file:moss.svg', dark: 'file:moss.svg' },
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Index documents and run semantic search with Moss',
		defaults: {
			name: 'Moss',
		},
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [
			{
				name: 'mossApi',
				required: true,
			},
		],
		properties: [
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'Add Documents',
						value: 'addDocs',
						description: 'Add or upsert documents into an existing index',
						action: 'Add documents',
					},
					{
						name: 'Create Index',
						value: 'createIndex',
						description: 'Create a new index from documents',
						action: 'Create an index',
					},
					{
						name: 'Delete Documents',
						value: 'deleteDocs',
						description: 'Delete documents from an index by ID',
						action: 'Delete documents',
					},
					{
						name: 'Delete Index',
						value: 'deleteIndex',
						description: 'Delete an index and all of its data',
						action: 'Delete an index',
					},
					{
						name: 'Get Documents',
						value: 'getDocs',
						description: 'Retrieve documents from an index',
						action: 'Get documents',
					},
					{
						name: 'Get Index',
						value: 'getIndex',
						description: 'Get metadata for a single index',
						action: 'Get an index',
					},
					{
						name: 'Get Job Status',
						value: 'getJobStatus',
						description: 'Check the status of an async index job',
						action: 'Get job status',
					},
					{
						name: 'List Indexes',
						value: 'listIndexes',
						description: 'List every index in the project',
						action: 'List indexes',
					},
					{
						name: 'Query',
						value: 'query',
						description: 'Run a semantic search against an index',
						action: 'Query an index',
					},
				],
				default: 'query',
			},
			{
				displayName: 'Index Name',
				name: 'indexName',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: {
						operation: [
							'createIndex',
							'addDocs',
							'query',
							'getIndex',
							'deleteIndex',
							'getDocs',
							'deleteDocs',
						],
					},
				},
				description: 'Name of the Moss index',
			},
			{
				displayName: 'Documents',
				name: 'documents',
				type: 'json',
				default: '[{"id":"doc1","text":"Your document text here"}]',
				required: true,
				displayOptions: {
					show: {
						operation: ['createIndex', 'addDocs'],
					},
				},
				description: 'JSON array of documents with id, text, and optional string metadata',
			},
			{
				displayName: 'Model ID',
				name: 'modelId',
				type: 'options',
				options: [
					{ name: 'moss-minilm (default)', value: 'moss-minilm' },
					{ name: 'moss-mediumlm', value: 'moss-mediumlm' },
				],
				default: 'moss-minilm',
				displayOptions: {
					show: {
						operation: ['createIndex'],
					},
				},
				description: 'Embedding model used when creating the index',
			},
			{
				displayName: 'Upsert',
				name: 'upsert',
				type: 'boolean',
				default: true,
				displayOptions: {
					show: {
						operation: ['addDocs'],
					},
				},
				description: 'Whether to update documents that already exist (matched by id)',
			},
			...waitProperties,
			{
				displayName: 'Query',
				name: 'query',
				type: 'string',
				default: '',
				required: true,
				typeOptions: {
					rows: 2,
				},
				displayOptions: {
					show: {
						operation: ['query'],
					},
				},
				description: 'Natural-language search query',
			},
			{
				displayName: 'Top K',
				name: 'topK',
				type: 'number',
				typeOptions: {
					minValue: 1,
					maxValue: 100,
				},
				default: 5,
				displayOptions: {
					show: {
						operation: ['query'],
					},
				},
				description: 'Maximum number of results to return',
			},
			{
				displayName: 'Document IDs',
				name: 'docIds',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: {
						operation: ['deleteDocs'],
					},
				},
				description: 'Comma-separated or JSON array of document IDs to delete',
			},
			{
				displayName: 'Document IDs',
				name: 'getDocIds',
				type: 'string',
				default: '',
				displayOptions: {
					show: {
						operation: ['getDocs'],
					},
				},
				description:
					'Optional comma-separated or JSON array of document IDs. Leave empty to fetch all.',
			},
			{
				displayName: 'Job ID',
				name: 'jobId',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: {
						operation: ['getJobStatus'],
					},
				},
				description: 'Job ID returned by create index, add documents, or delete documents',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];
		const credentials = await getMossCredentials.call(this);

		for (let itemIndex = 0; itemIndex < items.length; itemIndex++) {
			try {
				const operation = this.getNodeParameter('operation', itemIndex) as string;
				let responseData: IDataObject | IDataObject[] | unknown;

				const waitOptions = {
					waitForCompletion: this.getNodeParameter(
						'waitForCompletion',
						itemIndex,
						true,
					) as boolean,
					maxWaitSeconds: this.getNodeParameter('maxWaitSeconds', itemIndex, 300) as number,
				};

				switch (operation) {
					case 'createIndex': {
						const indexName = this.getNodeParameter('indexName', itemIndex) as string;
						const documents = parseDocuments(this.getNodeParameter('documents', itemIndex));
						const modelId = this.getNodeParameter('modelId', itemIndex) as string;
						responseData = await createIndex(
							credentials,
							indexName,
							documents,
							modelId,
							waitOptions,
						);
						break;
					}
					case 'addDocs': {
						const indexName = this.getNodeParameter('indexName', itemIndex) as string;
						const documents = parseDocuments(this.getNodeParameter('documents', itemIndex));
						const upsert = this.getNodeParameter('upsert', itemIndex) as boolean;
						responseData = await addDocs(
							credentials,
							indexName,
							documents,
							upsert,
							waitOptions,
						);
						break;
					}
					case 'query': {
						const indexName = this.getNodeParameter('indexName', itemIndex) as string;
						const query = this.getNodeParameter('query', itemIndex) as string;
						const topK = this.getNodeParameter('topK', itemIndex) as number;
						responseData = await queryIndex(credentials, indexName, query, topK);
						break;
					}
					case 'listIndexes': {
						responseData = await listIndexes(credentials);
						break;
					}
					case 'getIndex': {
						const indexName = this.getNodeParameter('indexName', itemIndex) as string;
						responseData = await getIndex(credentials, indexName);
						break;
					}
					case 'deleteIndex': {
						const indexName = this.getNodeParameter('indexName', itemIndex) as string;
						responseData = await deleteIndex(credentials, indexName);
						break;
					}
					case 'getDocs': {
						const indexName = this.getNodeParameter('indexName', itemIndex) as string;
						const docIds = parseStringList(this.getNodeParameter('getDocIds', itemIndex, ''));
						responseData = await getDocs(
							credentials,
							indexName,
							docIds.length ? docIds : undefined,
						);
						break;
					}
					case 'deleteDocs': {
						const indexName = this.getNodeParameter('indexName', itemIndex) as string;
						const docIds = parseStringList(this.getNodeParameter('docIds', itemIndex));
						responseData = await deleteDocs(credentials, indexName, docIds, waitOptions);
						break;
					}
					case 'getJobStatus': {
						const jobId = this.getNodeParameter('jobId', itemIndex) as string;
						responseData = await getJobStatus(credentials, jobId);
						break;
					}
					default:
						throw new NodeOperationError(this.getNode(), `Unknown operation: ${operation}`, {
							itemIndex,
						});
				}

				const executionData = this.helpers.constructExecutionMetaData(
					this.helpers.returnJsonArray(responseData as IDataObject | IDataObject[]),
					{ itemData: { item: itemIndex } },
				);
				returnData.push(...executionData);
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({
						json: {
							error: error instanceof Error ? error.message : String(error),
						},
						pairedItem: itemIndex,
					});
					continue;
				}
				if (error instanceof NodeOperationError) {
					throw error;
				}
				throw new NodeOperationError(
					this.getNode(),
					error instanceof Error ? error : new Error(String(error)),
					{ itemIndex },
				);
			}
		}

		return [returnData];
	}
}
