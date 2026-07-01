import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import type { JobCreate } from '@/types/project';

const POLLING_INTERVAL = 5000;

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: async () => {
      const response = await api.get('/jobs');
      return response.data;
    },
  });
}

export function useProjectStatus(id: string | null) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['projectStatus', id],
    queryFn: async () => {
      if (!id) return null;
      const response = await api.get(`/projects/${id}/status`);
      return response.data;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (
        data?.status === 'processing' ||
        data?.status === 'pending' ||
        data?.status === 'training'
      ) {
        return POLLING_INTERVAL;
      }
      return false;
    },
  });

  return { data, isLoading, error };
}

export function useCreateJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: JobCreate) => {
      const response = await api.post('/jobs', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });
}
