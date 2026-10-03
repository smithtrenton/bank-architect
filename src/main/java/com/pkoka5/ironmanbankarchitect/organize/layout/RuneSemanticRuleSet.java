package com.pkoka5.ironmanbankarchitect.organize.layout;

import java.util.ArrayList;
import com.pkoka5.ironmanbankarchitect.catalog.OrderedItemFamilies;
import com.pkoka5.ironmanbankarchitect.catalog.RequiredResource;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/** Exact canonical four-wide rune rows; non-rune entries remain ordinary dense spillover. */
public final class RuneSemanticRuleSet
{
	private static final String RULE_KEY = "runes.four-wide-rows";
	private static final RequiredResource<List<List<Integer>>> ROWS = new RequiredResource<>("rune rows",
		() -> Collections.unmodifiableList(new ArrayList<>(new OrderedItemFamilies(
			RuneSemanticRuleSet.class.getResourceAsStream(
				"/com/pkoka5/ironmanbankarchitect/catalog/rune-layout-families.tsv"), 0).entries().values())));

	private RuneSemanticRuleSet()
	{
	}

	public static LayoutRequest forEntries(List<LayoutEntry> entries)
	{
		return forEntries(entries, 0);
	}

	public static LayoutRequest forEntries(List<LayoutEntry> entries, int gridStartColumn)
	{
		Objects.requireNonNull(entries, "entries");
		return new LayoutRequest(gridStartColumn == 0 ? anchorFirstRune(entries) : entries,
			Collections.singletonList(ruleForRows(ROWS.get()))).withGridStartColumn(gridStartColumn);
	}

	static LayoutRequest forMainEntries(List<LayoutEntry> entries)
	{
		Objects.requireNonNull(entries, "entries");
		return new LayoutRequest(entries,
			Collections.singletonList(ruleForRows(mainRows(entries))));
	}

	static Integer firstPresentRuneId(List<LayoutEntry> entries)
	{
		Set<Integer> present = new LinkedHashSet<>();
		for (LayoutEntry entry : entries)
		{
			present.add(entry.getItem().getItemId());
		}
		for (List<Integer> row : ROWS.get())
		{
			for (Integer itemId : row)
			{
				if (present.contains(itemId)) return itemId;
			}
		}
		return null;
	}

	static List<List<Integer>> mainRows(List<LayoutEntry> entries)
	{
		Set<Integer> present = new LinkedHashSet<>();
		for (LayoutEntry entry : entries)
		{
			present.add(entry.getItem().getItemId());
		}
		List<List<Integer>> original = ROWS.get();
		List<List<Integer>> rows = new ArrayList<>();
		rows.add(original.get(0));
		rows.add(original.get(1));
		rows.add(original.get(2));
		List<Integer> tail = new ArrayList<>();
		for (int row = 3; row < original.size(); row++)
		{
			for (Integer itemId : original.get(row))
			{
				if (present.contains(itemId)) tail.add(itemId);
			}
		}
		if (present.contains(8013)) tail.add(8013);
		for (int offset = 0; offset < tail.size(); offset += 4)
		{
			rows.add(Collections.unmodifiableList(new ArrayList<>(
				tail.subList(offset, Math.min(offset + 4, tail.size())))));
		}
		return Collections.unmodifiableList(rows);
	}

	private static List<LayoutEntry> anchorFirstRune(List<LayoutEntry> entries)
	{
		for (LayoutEntry entry : entries)
		{
			if (entry.hasLockedTarget())
			{
				return entries;
			}
		}
		Integer firstRune = firstPresentRuneId(entries);
		if (firstRune != null)
		{
			List<LayoutEntry> anchored = new ArrayList<>(entries.size());
			for (LayoutEntry entry : entries)
			{
				anchored.add(entry.getItem().getItemId() == firstRune
					? entry.withLockedTarget(0) : entry);
			}
			return Collections.unmodifiableList(anchored);
		}
		return entries;
	}

	private static SemanticRule ruleForRows(List<List<Integer>> rows)
	{
		return SemanticRule.builder()
			.ruleKey(RULE_KEY)
			.atoms(atoms(rows))
			.confidenceTier(ConfidenceTier.HIGH)
			.shapePrimitive(ShapePrimitive.ROW_GROUP_MATRIX)
			.allowedWidths(Collections.singleton(4))
			.build();
	}

	private static List<SemanticAtom> atoms(List<List<Integer>> rows)
	{
		List<SemanticAtom> atoms = new ArrayList<>();
		for (int rowIndex = 0; rowIndex < rows.size(); rowIndex++)
		{
			List<SemanticAtom.Member> members = new ArrayList<>();
			for (int column = 0; column < rows.get(rowIndex).size(); column++)
			{
				members.add(new SemanticAtom.Member("rune-" + column, rows.get(rowIndex).get(column)));
			}
			atoms.add(new SemanticAtom("rune-row-" + rowIndex, members));
		}
		return atoms;
	}

}
