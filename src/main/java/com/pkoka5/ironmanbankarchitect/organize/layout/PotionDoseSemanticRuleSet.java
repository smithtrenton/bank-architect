package com.pkoka5.ironmanbankarchitect.organize.layout;

import com.pkoka5.ironmanbankarchitect.catalog.ItemSortMetadata;
import com.pkoka5.ironmanbankarchitect.catalog.ItemCategory;
import com.pkoka5.ironmanbankarchitect.catalog.ResourceItemSortMetadataCatalog;
import com.pkoka5.ironmanbankarchitect.catalog.RequiredResource;
import com.pkoka5.ironmanbankarchitect.catalog.OrderedItemFamilies;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/**
 * Exact canonical potion-dose families used by the supplies-category semantic layout. Each owned
 * family projects to a horizontal run in reviewed descending-dose order without name inference.
 */
public final class PotionDoseSemanticRuleSet
{
	private static final String RULE_KEY = "potion.dose-runs";
	private static final Set<Integer> ALL_WIDTHS = Collections.unmodifiableSet(
		new LinkedHashSet<>(Arrays.asList(1, 2, 3, 4, 5, 6, 7, 8)));

	private static final OrderedItemFamilies FAMILIES = new OrderedItemFamilies(
		PotionDoseSemanticRuleSet.class.getResourceAsStream(
			"/com/pkoka5/ironmanbankarchitect/catalog/potion-layout-families.tsv"), 0);
	private static final RequiredResource<Map<Integer, Integer>> MAX_DOSE_BY_ID =
		new RequiredResource<>("potion dose families", PotionDoseSemanticRuleSet::buildMaxDoseById);

	private PotionDoseSemanticRuleSet()
	{
	}

	/**
	 * Creates a request without claiming a dense current order or adding entry-level dense ranks.
	 */
	public static LayoutRequest forEntries(List<LayoutEntry> entries)
	{
		Objects.requireNonNull(entries, "entries");
		validateMetadata();
		return new LayoutRequest(entries, Collections.singletonList(buildRule()));
	}

	private static SemanticRule buildRule()
	{
		List<SemanticAtom> atoms = new ArrayList<>(FAMILIES.entries().size());
		for (Map.Entry<String, List<Integer>> family : FAMILIES.entries().entrySet())
		{
			List<SemanticAtom.Member> stages = new ArrayList<>(family.getValue().size());
			for (int index = 0; index < family.getValue().size(); index++)
			{
				int dose = family.getValue().size() - index;
				stages.add(new SemanticAtom.Member("dose-" + dose, family.getValue().get(index)));
			}
			atoms.add(new SemanticAtom(family.getKey(), stages));
		}

		return SemanticRule.builder()
			.ruleKey(RULE_KEY)
			.atoms(atoms)
			.confidenceTier(ConfidenceTier.HIGH)
			.shapePrimitive(ShapePrimitive.HORIZONTAL_RUN)
			.allowedWidths(ALL_WIDTHS)
			.build();
	}

	private static void validateMetadata()
	{
		MAX_DOSE_BY_ID.get();
	}

	private static Map<Integer, Integer> buildMaxDoseById()
	{
		Map<Integer, Integer> result = new LinkedHashMap<>();
		for (Map.Entry<String, List<Integer>> family : FAMILIES.entries().entrySet())
		{
			int max = family.getValue().size();
			if (max != 2 && max != 4)
				throw new IllegalStateException("Dose family must have two or four members: " + family.getKey());
			for (int index = 0; index < max; index++)
			{
				int itemId = family.getValue().get(index);
				ItemSortMetadata metadata = ResourceItemSortMetadataCatalog.INSTANCE.findById(itemId)
					.orElseThrow(() -> new IllegalStateException("Missing potion metadata for itemId " + itemId));
				if (!family.getKey().equals(metadata.getFamilyKey())
					|| metadata.getVariantKind() != ItemSortMetadata.VariantKind.DOSE
					|| metadata.getVariantValue() != max - index)
					throw new IllegalStateException("Dose family metadata mismatch for itemId " + itemId);
				result.put(itemId, max);
			}
		}
		return Collections.unmodifiableMap(result);
	}

	public static int maxDoseFor(int itemId)
	{
		return MAX_DOSE_BY_ID.get().getOrDefault(itemId, 0);
	}

	public static boolean isPartialDose(int itemId, ItemCategory category, String subcategory)
	{
		if (category != ItemCategory.POTION || subcategory == null) return false;
		String value = subcategory.trim().toLowerCase();
		String prefix = value.startsWith("potion-dose-") ? "potion-dose-"
			: value.startsWith("dose-") ? "dose-" : null;
		if (prefix == null) return false;
		int dose;
		try { dose = Integer.parseInt(value.substring(prefix.length())); }
		catch (NumberFormatException invalid) { return false; }
		if (dose < 1 || dose > 4) return false;
		ItemSortMetadata metadata = ResourceItemSortMetadataCatalog.INSTANCE.findById(itemId).orElse(null);
		return metadata != null && metadata.getVariantKind() == ItemSortMetadata.VariantKind.DOSE
			&& metadata.getVariantValue() == dose && dose < maxDoseFor(itemId);
	}
}
