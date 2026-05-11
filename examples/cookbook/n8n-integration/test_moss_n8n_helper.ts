import { MossN8NHelper } from './moss-n8n-helper';

// Mock MossClient for testing
const mockCreateIndex = jest.fn();
const mockAddDocs = jest.fn();
const mockDeleteDocs = jest.fn();
const mockQuery = jest.fn();
const mockLoadIndex = jest.fn();
const mockGetJobStatus = jest.fn();
const mockClose = jest.fn();

// Mock the MossClient class
jest.mock('@moss-dev/moss', () => {
  return {
    MossClient: jest.fn().mockImplementation(() => ({
      createIndex: mockCreateIndex,
      addDocs: mockAddDocs,
      deleteDocs: mockDeleteDocs,
      query: mockQuery,
      loadIndex: mockLoadIndex,
      getJobStatus: mockGetJobStatus,
      close: mockClose
    }))
  };
});

describe('MossN8NHelper', () => {
  let helper: MossN8NHelper;
  const projectId = 'test-project-id';
  const projectKey = 'test-project-key';

  beforeEach(() => {
    helper = new MossN8NHelper(projectId, projectKey);
    jest.clearAllMocks();
  });

  describe('createIndex', () => {
    it('should call MossClient.createIndex with correct parameters', async () => {
      const mockResult = {
        jobId: 'job-123',
        indexName: 'test-index',
        docCount: 2
      };
      mockCreateIndex.mockResolvedValue(mockResult);

      const docs = [
        { id: '1', text: 'Hello world', metadata: { source: 'test' } },
        { id: '2', text: 'Another doc', metadata: { source: 'test' } }
      ];

      const result = await helper.createIndex('test-index', docs);

      expect(mockCreateIndex).toHaveBeenCalledWith(
        'test-index',
        expect.arrayContaining([
          expect.objectContaining({ id: '1', text: 'Hello world' }),
          expect.objectContaining({ id: '2', text: 'Another doc' })
        ]),
        undefined
      );
      expect(result).toEqual(mockResult);
    });

    it('should handle options correctly', async () => {
      const mockResult = {
        jobId: 'job-123',
        indexName: 'test-index',
        docCount: 1
      };
      mockCreateIndex.mockResolvedValue(mockResult);

      const docs = [{ id: '1', text: 'Test doc' }];
      const options = { modelId: 'custom-model' };

      await helper.createIndex('test-index', docs, options);

      expect(mockCreateIndex).toHaveBeenCalledWith(
        'test-index',
        expect.any(Array),
        options
      );
    });
  });

  describe('addDocs', () => {
    it('should call MossClient.addDocs with correct parameters', async () => {
      const mockResult = {
        jobId: 'job-456',
        indexName: 'test-index',
        docCount: 5
      };
      mockAddDocs.mockResolvedValue(mockResult);

      const docs = [
        { id: '3', text: 'New doc', metadata: { source: 'api' } }
      ];

      const result = await helper.addDocs('test-index', docs);

      expect(mockAddDocs).toHaveBeenCalledWith(
        'test-index',
        expect.arrayContaining([
          expect.objectContaining({ id: '3', text: 'New doc' })
        ]),
        undefined
      );
      expect(result).toEqual(mockResult);
    });

    it('should handle upsert option', async () => {
      const mockResult = {
        jobId: 'job-456',
        indexName: 'test-index',
        docCount: 3
      };
      mockAddDocs.mockResolvedValue(mockResult);

      const docs = [{ id: '1', text: 'Updated doc' }];
      const options = { upsert: true };

      await helper.addDocs('test-index', docs, options);

      expect(mockAddDocs).toHaveBeenCalledWith(
        'test-index',
        expect.any(Array),
        options
      );
    });
  });

  describe('deleteDocs', () => {
    it('should call MossClient.deleteDocs with correct parameters', async () => {
      const mockResult = {
        jobId: 'job-789',
        indexName: 'test-index',
        docCount: 0
      };
      mockDeleteDocs.mockResolvedValue(mockResult);

      const docIds = ['1', '2'];
      const result = await helper.deleteDocs('test-index', docIds);

      expect(mockDeleteDocs).toHaveBeenCalledWith('test-index', ['1', '2'], undefined);
      expect(result).toEqual(mockResult);
    });
  });

  describe('query', () => {
    it('should call MossClient.query and return formatted results', async () => {
      const mockSearchResult = {
        docs: [
          {
            id: 'doc1',
            text: 'Test document',
            metadata: { category: 'test' },
            score: 0.95
          }
        ],
        query: 'test query',
        timeTakenInMs: 5
      };
      mockQuery.mockResolvedValue(mockSearchResult);

      const results = await helper.query('test-index', 'test query', { topK: 5 });

      expect(mockQuery).toHaveBeenCalledWith('test-index', 'test query', { topK: 5 });
      expect(results).toEqual([
        {
          id: 'doc1',
          text: 'Test document',
          metadata: { category: 'test' },
          score: 0.95
        }
      ]);
    });

    it('should use default topK when not provided', async () => {
      const mockSearchResult = {
        docs: [],
        query: 'test',
        timeTakenInMs: 2
      };
      mockQuery.mockResolvedValue(mockSearchResult);

      await helper.query('test-index', 'test');

      expect(mockQuery).toHaveBeenCalledWith('test-index', 'test', { topK: 10 }); // default value
    });
  });

  describe('loadIndex', () => {
    it('should call MossClient.loadIndex', async () => {
      const mockResult = 'test-index';
      mockLoadIndex.mockResolvedValue(mockResult);

      const result = await helper.loadIndex('test-index');

      expect(mockLoadIndex).toHaveBeenCalledWith('test-index', undefined);
      expect(result).toBe(mockResult);
    });

    it('should pass options to MossClient.loadIndex', async () => {
      const mockResult = 'test-index';
      mockLoadIndex.mockResolvedValue(mockResult);
      const options = { autoRefresh: true, pollingIntervalInSeconds: 300 };

      await helper.loadIndex('test-index', options);

      expect(mockLoadIndex).toHaveBeenCalledWith('test-index', options);
    });
  });

  describe('getJobStatus', () => {
    it('should call MossClient.getJobStatus and return formatted response', async () => {
      const mockStatus = {
        jobId: 'job-123',
        status: 'completed',
        progress: 100,
        currentPhase: undefined,
        error: undefined,
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:05:00Z'
      };
      mockGetJobStatus.mockResolvedValue(mockStatus);

      const result = await helper.getJobStatus('job-123');

      expect(mockGetJobStatus).toHaveBeenCalledWith('job-123');
      expect(result).toEqual({
        status: 'completed',
        progress: 100,
        currentPhase: undefined,
        error: undefined
      });
    });
  });

  describe('close', () => {
    it('should call MossClient.close', () => {
      helper.close();
      expect(mockClose).toHaveBeenCalled();
    });
  });
});