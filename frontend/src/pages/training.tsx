import React from 'react';
import Layout from '../components/Layout';
import Training from '../modules/Training';
import ProtectedRoute from '../components/ProtectedRoute';

const TrainingPage: React.FC = () => {
  return (
    <ProtectedRoute>
      <Layout>
        <Training />
      </Layout>
    </ProtectedRoute>
  );
};

export default TrainingPage;