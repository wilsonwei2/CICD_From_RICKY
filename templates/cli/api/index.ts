import axios from 'axios';

const API_VERSION = '/v0';
const TEMPLATE_API = `${API_VERSION}/d/templates`;

/* eslint-disable camelcase */
interface AuthResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  scope: string;
  token_type: string;
}

interface ListResponse {
  data: {
    id: string;
  }[]
}
/* eslint-enable camelcase */

const getEntityList = async (entityName: string): Promise<string[]> => {
  const response = await axios.get<ListResponse>(`${TEMPLATE_API}/${entityName}`);
  return response.data.data.map(({ id }) => id);
};

const getEntity = async (uriPart: string): Promise<string> => {
  const response = await axios.get<string>(`${TEMPLATE_API}${uriPart}`, {
    transformRequest: (data) => data,
  });
  return response.data;
};

const updateEntity = async (uriPart: string, data: string): Promise<void> => {
  await axios.put<string>(`${TEMPLATE_API}${uriPart}`, data);
};

export const auth = async (username: string, password: string): Promise<string> => {
  const response = await axios.post<AuthResponse>('/v0/token', {
    username,
    password,
    grant_type: 'password',
  });
  return response.data.access_token;
};

export const getTemplates = async (): Promise<string[]> => getEntityList('templates');

export const getTemplate = async (template: string,
  locale: string): Promise<string> => getEntity(`/templates/${template}/localization/${locale}`);

export const updateTemplate = async (template: string, locale: string,
  data: string): Promise<void> => updateEntity(`/templates/${template}/localization/${locale}`, data);

export const getSampleData = async (template: string): Promise<Record<string, unknown>> => {
  const response = await axios.get<Record<string, unknown>>(`${TEMPLATE_API}/templates/${template}/sample_data`);
  return response.data;
};

export const getSampleDataDocumentation = async (template: string): Promise<string> => {
  const response = await axios.get<string>(`${TEMPLATE_API}/templates/${template}/documentation`);
  return response.data;
};

export const previewDocument = async (template: string, locale: string, templateData: string,
  sampleData: Record<string, unknown>, contentType = 'html'): Promise<string> => {
  const response = await axios.post<string>(`${TEMPLATE_API}/templates/${template}/preview`,
    JSON.stringify({
      template: templateData,
      data: sampleData,
      locale,
      content_type: contentType,
    }));
  return response.data;
};

export const getStyles = async (): Promise<string[]> => getEntityList('styles');

export const getStyle = async (style: string): Promise<string> => getEntity(`/styles/${style}`);

export const updateStyle = async (style: string,
  styleData: string): Promise<void> => updateEntity(`/styles/${style}`, styleData);
