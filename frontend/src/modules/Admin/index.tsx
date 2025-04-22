import React from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Settings, Users, Database, Shield, Book, Brain } from 'lucide-react';
import AISettingsPanel from './AISettingsPanel';
import RagSettingsPanel from './RagSettingsPanel';
import ModelTrainingPanel from './ModelTrainingPanel';
import useAuthStore from '../../store/authStore';

const AdminPanel: React.FC = () => {
  const { user } = useAuthStore();

  // Only admins can access this panel
  if (user?.role !== 'admin') {
    return (
      <div className="p-8 text-center">
        <Shield className="mx-auto h-12 w-12 text-yellow-500 mb-4" />
        <h3 className="text-lg font-medium mb-2">Access Restricted</h3>
        <p className="text-gray-500">
          This section requires administrative privileges.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Admin Panel</CardTitle>
          <CardDescription>
            System configuration and administrative settings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="ai-settings" className="space-y-4">
            <TabsList>
              <TabsTrigger value="ai-settings" className="flex items-center gap-2">
                <Settings className="h-4 w-4" />
                AI Settings
              </TabsTrigger>
              <TabsTrigger value="rag-settings" className="flex items-center gap-2">
                <Book className="h-4 w-4" />
                Knowledge Base
              </TabsTrigger>
              <TabsTrigger value="model-training" className="flex items-center gap-2">
                <Brain className="h-4 w-4" />
                Fine-Tuned Models
              </TabsTrigger>
              <TabsTrigger value="users" className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                User Management
              </TabsTrigger>
              <TabsTrigger value="system" className="flex items-center gap-2">
                <Database className="h-4 w-4" />
                System Settings
              </TabsTrigger>
            </TabsList>
            <TabsContent value="ai-settings">
              <AISettingsPanel />
            </TabsContent>
            <TabsContent value="rag-settings">
              <RagSettingsPanel />
            </TabsContent>
            <TabsContent value="model-training">
              <ModelTrainingPanel />
            </TabsContent>
            <TabsContent value="users">
              <div className="p-4 border border-dashed rounded-md text-center text-gray-500">
                User management panel will be implemented in a future update.
              </div>
            </TabsContent>
            <TabsContent value="system">
              <div className="p-4 border border-dashed rounded-md text-center text-gray-500">
                System settings panel will be implemented in a future update.
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};

export default AdminPanel;