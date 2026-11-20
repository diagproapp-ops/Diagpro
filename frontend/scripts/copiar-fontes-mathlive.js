// Copia as fontes do editor de equações (MathLive) para public/, para o DiagPro servi-las ele mesmo
// (nada é carregado de CDN externo). Roda sozinho depois do "npm install" e antes do start/build.
const fs = require('fs');
const path = require('path');

const origem = path.join(__dirname, '..', 'node_modules', 'mathlive', 'fonts');
const destino = path.join(__dirname, '..', 'public', 'mathlive', 'fonts');

if (!fs.existsSync(origem)) {
  console.warn('[mathlive] fontes não encontradas em node_modules; rode "npm install".');
  process.exit(0);
}
fs.mkdirSync(destino, { recursive: true });
let n = 0;
for (const nome of fs.readdirSync(origem)) {
  if (!/\.woff2$/i.test(nome)) continue;
  fs.copyFileSync(path.join(origem, nome), path.join(destino, nome));
  n += 1;
}
console.log(`[mathlive] ${n} fontes copiadas para public/mathlive/fonts`);
