# Examples

This page contains various examples of how to use the package.

## Basic Example

Here's a basic example:

```javascript
import { sync } from 'my-package'

await sync({
  root: './docs'
})
```

## Advanced Example

For more advanced usage:

```javascript
import { sync } from 'my-package'

await sync({
  root: './docs',
  creds: {
    projectId: 'your-id',
    projectKey: 'your-key',
    indexName: 'your-index'
  }
})
```

## Configuration Options

### Root Directory

Specify the root directory for your documentation.

### Credentials

Provide your Moss project credentials.

## Troubleshooting

If you encounter issues:

1. Check your environment variables
2. Verify your credentials
3. Ensure the docs directory exists

