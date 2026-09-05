import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { AppLayout, DashboardPage, NotFoundPage, RouteErrorPage } from './App';
import { AuthProvider } from './auth';
import { ClientDetailPage, ClientFormPage, ClientsPage } from './clients';
import { DocumentsPage, ReviewPage, UploadPage } from './documents';
import { PoliciesPage, PolicyDetailPage, PolicyFormPage } from './policies';
import { MailboxPage, MessagePage } from './mailbox';
import './styles.css';

const router = createBrowserRouter([
  {
    element: (
      <AuthProvider>
        <AppLayout />
      </AuthProvider>
    ),
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'clients', element: <ClientsPage /> },
      { path: 'clients/new', element: <ClientFormPage /> },
      { path: 'clients/:id', element: <ClientDetailPage /> },
      { path: 'clients/:id/edit', element: <ClientFormPage /> },
      { path: 'clients/:id/upload', element: <UploadPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'documents/new', element: <UploadPage /> },
      { path: 'documents/:id', element: <ReviewPage /> },
      { path: 'mailbox', element: <MailboxPage /> },
      { path: 'mailbox/:id', element: <MessagePage /> },
      { path: 'policies', element: <PoliciesPage /> },
      { path: 'policies/new', element: <PolicyFormPage /> },
      { path: 'policies/:id', element: <PolicyDetailPage /> },
      { path: 'policies/:id/edit', element: <PolicyFormPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
