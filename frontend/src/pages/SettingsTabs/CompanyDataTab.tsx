import React, { useState, useEffect, useRef } from 'react';
import { Box, Typography, TextField, Button, Stack, Avatar } from '@mui/material';
import api from '../../api';

export default function CompanyDataTab() {
  const [company, setCompany] = useState({
    company_name: '',
    company_cnpj: '',
    company_address: '',
    company_phone: '',
    company_email: '',
    company_website: '',
    company_logo_path: ''
  });
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.get('/company').then(res => {
      setCompany(res.data);
      setLogoPreview(res.data.company_logo_path || null);
    });
  }, []);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setCompany({ ...company, [e.target.name]: e.target.value });
  }

  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      setLogoFile(file);
      setLogoPreview(URL.createObjectURL(file));
    }
  }

  function handleUploadClick() {
    fileInputRef.current?.click();
  }

  function handleSave() {
    const formData = new FormData();
    formData.append('company_name', company.company_name);
    formData.append('company_cnpj', company.company_cnpj);
    formData.append('company_address', company.company_address);
    formData.append('company_phone', company.company_phone);
    formData.append('company_email', company.company_email);
    formData.append('company_website', company.company_website);
    if (logoFile) {
      formData.append('logo', logoFile);
    }
    api.put('/company', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(res => {
      setCompany(res.data);
      setLogoPreview(res.data.company_logo_path || null);
      setLogoFile(null);
      alert('Dados salvos!');
    });
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>Dados da Empresa</Typography>
      <Stack spacing={2} sx={{ maxWidth: 400 }}>
        <TextField label="Nome da Empresa" name="company_name" value={company.company_name} onChange={handleChange} />
        <TextField label="CNPJ" name="company_cnpj" value={company.company_cnpj} onChange={handleChange} />
        <TextField label="Endereço" name="company_address" value={company.company_address} onChange={handleChange} />
        <TextField label="Telefone/Celular" name="company_phone" value={company.company_phone} onChange={handleChange} />
        <TextField label="Email de Contato" name="company_email" value={company.company_email} onChange={handleChange} />
        <TextField label="Website" name="company_website" value={company.company_website} onChange={handleChange} />
        <Box>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Logo da empresa
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <Avatar
              variant="square"
              src={logoPreview || undefined}
              sx={{ width: 80, height: 80, bgcolor: 'action.hover', border: '1px solid', borderColor: 'divider' }}
            >
              {/* Se não tiver logo, mostra um ícone genérico */}
              {(!logoPreview) && <span style={{ fontSize: 18, color: '#aaa' }}>Logo</span>}
            </Avatar>
            <Button variant="outlined" onClick={handleUploadClick}>
              {logoFile ? 'Alterar Logo' : (logoPreview ? 'Trocar Logo' : 'Escolher Logo')}
            </Button>
            <input
              type="file"
              accept="image/*"
              ref={fileInputRef}
              style={{ display: 'none' }}
              onChange={handleLogoChange}
            />
          </Stack>
          <Typography variant="caption" color="textSecondary">
            Imagem PNG ou JPG. O logo aparecerá nos relatórios.
          </Typography>
        </Box>
        <Button variant="contained" color="primary" onClick={handleSave}>Salvar Dados</Button>
      </Stack>
    </Box>
  );
}