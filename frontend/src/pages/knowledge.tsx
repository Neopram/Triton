import React from 'react';
import Layout from '../components/Layout';
import KnowledgeBase from '../modules/KnowledgeBase';
import ProtectedRoute from '../components/ProtectedRoute';
import { useAuthStore } from '../store/authStore';

const KnowledgePage: React.FC = () => {
  const { user } = useAuthStore();
  
  return (
    <ProtectedRoute>
      <Layout>
        <KnowledgeBase />
      </Layout>
    </ProtectedRoute>
  );
};

export default KnowledgePage;