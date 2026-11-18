export interface Cargo {
  id_cargo: string;
  nome_cargo: string;
}

export interface Evento {
  id_evento: string;
  identificador_evento: string;   // <-- ADICIONE!
  nome_evento: string;
  data_prova: string | null;
  status: string | null;
  numero_edital?: string | null;   // <-- ADICIONE!
  local_prova?: string | null;     // <-- ADICIONE!
  observacoes?: string | null;     // <-- ADICIONE!
  cargos: Cargo[];
}

// --- ADICIONE ESTA INTERFACE ---
export interface User {
  id: number;
  username: string;
  email: string | null;
  role: string;
  tenant_id?: number;
  full_name?: string; // <-- Adicione esta linha!
}