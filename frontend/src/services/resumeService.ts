import api from './api';
import type { ResumeUploadResponse, ResumeStatus } from '@/types';

export async function uploadResumes(
  files: File[],
  jobId: string
): Promise<ResumeUploadResponse[]> {
  // Single batch request — all files in one multipart POST
  const form = new FormData();
  for (const file of files) {
    form.append('files', file);
  }
  const { data } = await api.post<ResumeUploadResponse[]>(
    '/resumes/upload/batch',
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { job_id: jobId },
    },
  );
  return data;
}

export async function getResumeStatus(resumeId: string): Promise<ResumeStatus> {
  const { data } = await api.get<ResumeStatus>(`/resumes/${resumeId}/status`);
  return data;
}
