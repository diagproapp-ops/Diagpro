import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;
import org.apache.pdfbox.pdmodel.interactive.form.PDField;
import org.apache.pdfbox.Loader; // Importante para PDFBox 3.x
import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.file.Files;
import java.nio.file.Paths;

public class PreencheCapaPDF_JSON_PDFBox {
    public static void main(String[] args) throws Exception {
        String templatePath = args[0];
        String dadosJson = args[1];
        String saidaDir = args[2];

        Files.createDirectories(Paths.get(saidaDir));
        String jsonString = new String(Files.readAllBytes(Paths.get(dadosJson)), "UTF-8");
        JSONArray capas = new JSONArray(jsonString);

        for (int i = 0; i < capas.length(); i++) {
            JSONObject dados = capas.getJSONObject(i);
            String nomeArquivo = dados.optString("Inscricao", "candidato") + "_capa.pdf";
            // PDFBox 3.x: use Loader.loadPDF
            PDDocument pdfDoc = Loader.loadPDF(Paths.get(templatePath).toFile());
            PDAcroForm acroForm = pdfDoc.getDocumentCatalog().getAcroForm();

            for (String key : dados.keySet()) {
                PDField field = acroForm.getField(key);
                if (field != null) field.setValue(dados.getString(key));
            }

            acroForm.flatten();
            pdfDoc.save(Paths.get(saidaDir, nomeArquivo).toString());
            pdfDoc.close();
        }
        System.out.println("Capas PDF preenchidas!");
    }
}