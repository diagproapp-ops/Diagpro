module.exports = function override(config, env) {
  // Exclui SVGs do CKEditor5 do SVGR
  const svgRule = config.module.rules.find(rule => rule.test && rule.test.toString().includes('svg'));
  if (svgRule) {
    svgRule.exclude = [
      /ckeditor5-[^/\\]+[/\\]theme[/\\]icons[/\\][^/\\]+\.svg$/,
    ];
  }
  // Adiciona loader "raw-loader" para SVGs do CKEditor5
  config.module.rules.push({
    test: /ckeditor5-[^/\\]+[/\\]theme[/\\]icons[/\\][^/\\]+\.svg$/,
    use: ['raw-loader'],
  });
  return config;
};