import type {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
	Icon,
} from 'n8n-workflow';

export class MossApi implements ICredentialType {
	name = 'mossApi';

	displayName = 'Moss API';

	documentationUrl = 'https://docs.moss.dev/docs/integrate/authentication';

	icon: Icon = { light: 'file:../icons/moss.svg', dark: 'file:../icons/moss.svg' };

	properties: INodeProperties[] = [
		{
			displayName: 'Project ID',
			name: 'projectId',
			type: 'string',
			default: '',
			required: true,
			description: 'Moss project ID from the Moss Portal',
		},
		{
			displayName: 'Project Key',
			name: 'projectKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			description: 'Moss project access key from the Moss Portal',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				'x-project-key': '={{$credentials.projectKey}}',
				'x-service-version': 'v1',
				'Content-Type': 'application/json',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: 'https://service.usemoss.dev/v1',
			url: '/manage',
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'x-project-key': '={{$credentials.projectKey}}',
				'x-service-version': 'v1',
			},
			body: {
				action: 'listIndexes',
				projectId: '={{$credentials.projectId}}',
			},
		},
	};
}
