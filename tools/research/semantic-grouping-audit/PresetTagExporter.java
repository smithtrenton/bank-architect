import com.pkoka5.ironmanbankarchitect.catalog.CatalogItem;
import com.pkoka5.ironmanbankarchitect.catalog.CompositeItemCatalog;
import com.pkoka5.ironmanbankarchitect.organize.BankPresets;
import com.pkoka5.ironmanbankarchitect.organize.BankTags;
import com.pkoka5.ironmanbankarchitect.organize.PresetCategoryMapper;
import com.pkoka5.ironmanbankarchitect.organize.layout.PotionDoseSemanticRuleSet;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/** Offline research helper; located outside plugin and test source sets. */
public final class PresetTagExporter
{
 public static void main(String[] args) throws Exception
 {
  Path effective = Paths.get(args[0]);
  Path output = Paths.get(args[1]);
  List<String> rows = Files.readAllLines(effective, StandardCharsets.UTF_8);
  List<String> result = new ArrayList<>();
  result.add("item_id\tpreset_category\tpreset_tag\tpreset_tag_by_family");
  for (String row : rows.subList(1, rows.size()))
  {
   int id = Integer.parseInt(row.split("\t", 2)[0]);
   CatalogItem item = CompositeItemCatalog.DEFAULT.describeOrUnknown(id);
   String category = PresetCategoryMapper.map(BankPresets.IRONMAN, item, true).getKey();
   String subcategory = item.getSubcategory();
   String tag = BankTags.tagFor(category, subcategory).getKey();
   boolean partialDose = PotionDoseSemanticRuleSet.isPartialDose(id, item.getCategory(), subcategory);
   result.add(id + "\t" + category + "\t" + tag + "\t" + (partialDose ? "potions" : tag));
  }
  Files.createDirectories(output.toAbsolutePath().getParent());
  Files.write(output, result, StandardCharsets.UTF_8);
  System.out.println("Exported preset tags for " + (result.size() - 1) + " exact IDs.");
 }
}
