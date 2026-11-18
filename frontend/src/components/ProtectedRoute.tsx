import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate, Outlet, useParams } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';

interface ProtectedRouteProps {
  allowedRoles?: string[]; // Exemplo: ['admin', 'coordenador', 'professor']
  onlyProfessorContent?: boolean; // se true, só professor pode acessar
}

/**
 * Protege rotas por autenticação e papel do usuário.
 * - Se não estiver autenticado, redireciona para login.
 * - Se houver restrição de role, só permite acesso se o usuário estiver na lista.
 * - Se for professor, só deixa acessar páginas de conteúdo, redirecionando para lá se tentar acessar outras.
 */
const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  allowedRoles,
  onlyProfessorContent
}) => {
  const { isAuthenticated, loading, user } = useAuth();
  const { eventId } = useParams();

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Se é rota exclusiva para professor e não é professor, bloqueia
  if (onlyProfessorContent && (!user || user.role !== 'professor')) {
    return <Navigate to="/" replace />;
  }

  // Se há restrição de role e o usuário não está autorizado
  if (
    allowedRoles &&
    (!user || !allowedRoles.includes(user.role))
  ) {
    // Se for professor, força para página de conteúdos vinculados
    if (user && user.role === 'professor') {
      // Se eventId não existir, pode mandar para uma tela de erro ou home
      return <Navigate to={eventId ? `/eventos/${eventId}/conteudo` : "/"} replace />;
    }
    // Outros usuários não autorizados vão para home
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;