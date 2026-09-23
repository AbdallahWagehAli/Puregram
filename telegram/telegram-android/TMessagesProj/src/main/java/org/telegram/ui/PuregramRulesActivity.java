package org.telegram.ui;

import android.content.Context;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;

import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.telegram.messenger.AndroidUtilities;
import org.telegram.messenger.LocaleController;
import org.telegram.messenger.PuregramRules;
import org.telegram.messenger.R;
import org.telegram.ui.ActionBar.ActionBar;
import org.telegram.ui.ActionBar.AlertDialog;
import org.telegram.ui.ActionBar.BaseFragment;
import org.telegram.ui.ActionBar.Theme;
import org.telegram.ui.Cells.HeaderCell;
import org.telegram.ui.Cells.TextInfoPrivacyCell;
import org.telegram.ui.Cells.TextSettingsCell;
import org.telegram.ui.Components.LayoutHelper;
import org.telegram.ui.Components.RecyclerListView;

import java.util.ArrayList;

/**
 * Puregram — the user's own allow / block lists (POLICY_SPEC.md §7).
 *
 * <p>People always open. Channels, bots and groups stay closed until the user
 * allows them. An allow can be withdrawn; a block is permanent, so this screen
 * offers no control that would undo one — the blocked section is read-only and
 * says why.
 *
 * <p>Chats normally reach these lists from the refusal dialog. "Add by link"
 * exists for the other case: a list of links to deal with in one go, without
 * opening any of them.
 */
public class PuregramRulesActivity extends BaseFragment {

    private RecyclerListView listView;
    private ListAdapter adapter;

    private ArrayList<PuregramRules.Rule> allowed = new ArrayList<>();
    private ArrayList<PuregramRules.Rule> blocked = new ArrayList<>();

    private int statusRow;
    private int addRow;
    private int addInfoRow;
    private int allowedHeaderRow;
    private int allowedStartRow;
    private int allowedEndRow;
    private int allowedInfoRow;
    private int blockedHeaderRow;
    private int blockedStartRow;
    private int blockedEndRow;
    private int blockedInfoRow;
    private int eraseRow;
    private int eraseInfoRow;
    private int rowCount;

    @Override
    public boolean onFragmentCreate() {
        super.onFragmentCreate();
        updateRows();
        return true;
    }

    private void updateRows() {
        final PuregramRules rules = PuregramRules.getInstance();
        allowed = rules.rulesOf(currentAccount, PuregramRules.RULE_ALLOW);
        blocked = rules.rulesOf(currentAccount, PuregramRules.RULE_BLOCK);

        rowCount = 0;
        statusRow = rowCount++;
        addRow = rowCount++;
        addInfoRow = rowCount++;

        allowedHeaderRow = rowCount++;
        if (allowed.isEmpty()) {
            allowedStartRow = allowedEndRow = -1;
        } else {
            allowedStartRow = rowCount;
            rowCount += allowed.size();
            allowedEndRow = rowCount;
        }
        allowedInfoRow = rowCount++;

        blockedHeaderRow = rowCount++;
        if (blocked.isEmpty()) {
            blockedStartRow = blockedEndRow = -1;
        } else {
            blockedStartRow = rowCount;
            rowCount += blocked.size();
            blockedEndRow = rowCount;
        }
        blockedInfoRow = rowCount++;

        eraseRow = rowCount++;
        eraseInfoRow = rowCount++;
    }

    private void refresh() {
        updateRows();
        if (adapter != null) {
            adapter.notifyDataSetChanged();
        }
    }

    @Override
    public View createView(Context context) {
        actionBar.setBackButtonImage(R.drawable.ic_ab_back);
        actionBar.setAllowOverlayTitle(true);
        actionBar.setTitle(PuregramRules.str(R.string.PuregramRules));
        actionBar.setActionBarMenuOnItemClick(new ActionBar.ActionBarMenuOnItemClick() {
            @Override
            public void onItemClick(int id) {
                if (id == -1) {
                    finishFragment();
                }
            }
        });

        fragmentView = new FrameLayout(context);
        FrameLayout frameLayout = (FrameLayout) fragmentView;
        frameLayout.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundGray));

        listView = new RecyclerListView(context);
        listView.setFocusable(true);
        listView.setLayoutManager(new LinearLayoutManager(context, LinearLayoutManager.VERTICAL, false));
        listView.setAdapter(adapter = new ListAdapter(context));
        frameLayout.addView(listView, LayoutHelper.createFrame(
                LayoutHelper.MATCH_PARENT, LayoutHelper.MATCH_PARENT));

        listView.setOnItemClickListener((view, position) -> {
            if (position == addRow) {
                showAddDialog();
            } else if (allowedStartRow != -1 && position >= allowedStartRow && position < allowedEndRow) {
                onAllowedClicked(allowed.get(position - allowedStartRow));
            } else if (blockedStartRow != -1 && position >= blockedStartRow && position < blockedEndRow) {
                showToast(PuregramRules.str(R.string.PuregramCannotUnblock));
            } else if (position == eraseRow) {
                onEraseClicked();
            }
        });
        return fragmentView;
    }

    /**
     * Paste a list of links or usernames and deal with them in one go. Each line
     * is resolved to a real chat before a rule is written, so the rule matches
     * the same chat the gate sees.
     */
    private void showAddDialog() {
        if (getParentActivity() == null) {
            return;
        }
        final LinearLayout layout = new LinearLayout(getParentActivity());
        layout.setOrientation(LinearLayout.VERTICAL);

        final EditText field = new EditText(getParentActivity());
        field.setTextColor(Theme.getColor(Theme.key_dialogTextBlack));
        field.setHintTextColor(Theme.getColor(Theme.key_dialogTextHint));
        field.setBackgroundDrawable(null);
        field.setGravity(LocaleController.isRTL ? Gravity.RIGHT : Gravity.LEFT);
        field.setSingleLine(false);
        field.setMinLines(3);
        field.setMaxLines(8);
        field.setHint(PuregramRules.str(R.string.PuregramAddHint));
        field.setTextSize(android.util.TypedValue.COMPLEX_UNIT_DIP, 16);
        layout.addView(field, LayoutHelper.createLinear(
                LayoutHelper.MATCH_PARENT, LayoutHelper.WRAP_CONTENT, 24, 8, 24, 0));

        final AlertDialog.Builder builder = new AlertDialog.Builder(getParentActivity())
                .setTitle(PuregramRules.str(R.string.PuregramAddManually))
                .setMessage(PuregramRules.str(R.string.PuregramAddManuallyInfo))
                .setView(layout)
                .setPositiveButton(PuregramRules.str(R.string.PuregramAddAllowAll),
                        (d, w) -> applyPasted(field.getText().toString(), PuregramRules.RULE_ALLOW))
                .setNeutralButton(PuregramRules.str(R.string.PuregramAddBlockAll),
                        (d, w) -> confirmPastedBlock(field.getText().toString()))
                .setNegativeButton(PuregramRules.str(R.string.PuregramCancel),
                        (d, w) -> d.dismiss());
        showDialog(builder.create());
    }

    /** Blocking a whole list is still irreversible, so it is still confirmed. */
    private void confirmPastedBlock(String text) {
        final int count = PuregramRules.countTargets(text);
        if (count == 0) {
            showToast(PuregramRules.str(R.string.PuregramAddNothing));
            return;
        }
        if (getParentActivity() == null) {
            return;
        }
        showDialog(new AlertDialog.Builder(getParentActivity())
                .setTitle(PuregramRules.str(R.string.PuregramBlockConfirmTitle))
                .setMessage(LocaleController.formatString(R.string.PuregramAddBlockConfirm, count))
                .setPositiveButton(PuregramRules.str(R.string.PuregramBlockForever),
                        (d, w) -> applyPasted(text, PuregramRules.RULE_BLOCK))
                .setNegativeButton(PuregramRules.str(R.string.PuregramCancel),
                        (d, w) -> d.dismiss())
                .create());
    }

    private void applyPasted(String text, String rule) {
        if (PuregramRules.countTargets(text) == 0) {
            showToast(PuregramRules.str(R.string.PuregramAddNothing));
            return;
        }
        showToast(PuregramRules.str(R.string.PuregramAddWorking));
        PuregramRules.getInstance().addByText(currentAccount, text, rule, (added, failed) -> {
            refresh();
            showToast(LocaleController.formatString(R.string.PuregramAddResult, added, failed));
        });
    }

    /** An allowed chat can be tightened two ways — never loosened further. */
    private void onAllowedClicked(PuregramRules.Rule rule) {
        if (getParentActivity() == null) {
            return;
        }
        showDialog(new AlertDialog.Builder(getParentActivity())
                .setTitle(displayName(rule))
                .setItems(new CharSequence[]{
                        PuregramRules.str(R.string.PuregramWithdraw),
                        PuregramRules.str(R.string.PuregramBlockForever),
                }, (dialog, which) -> {
                    if (which == 0) {
                        PuregramRules.getInstance().withdraw(currentAccount, rule.chatId);
                        refresh();
                    } else {
                        PuregramRules.getInstance()
                                .confirmBlock(currentAccount, rule.chatId, this::refresh);
                    }
                })
                .create());
    }

    /**
     * The data-deletion path Google Play requires. It is scheduled, not instant:
     * erasing the rules also clears the permanent blocks, so an immediate button
     * would be a one-tap way around them.
     */
    private void onEraseClicked() {
        if (getParentActivity() == null) {
            return;
        }
        final String pending = PuregramRules.getInstance().erasureEffectiveAt(currentAccount);
        if (!TextUtils.isEmpty(pending)) {
            showDialog(new AlertDialog.Builder(getParentActivity())
                    .setTitle(PuregramRules.str(R.string.PuregramDeleteScheduled))
                    .setMessage(LocaleController.formatString(
                            R.string.PuregramDeleteScheduledBody, formatDate(pending)))
                    .setPositiveButton(PuregramRules.str(R.string.PuregramDeleteCancel),
                            (d, w) -> PuregramRules.getInstance()
                                    .cancelErasure(currentAccount, this::refresh))
                    .setNegativeButton(PuregramRules.str(R.string.PuregramClose),
                            (d, w) -> d.dismiss())
                    .create());
            return;
        }
        showDialog(new AlertDialog.Builder(getParentActivity())
                .setTitle(PuregramRules.str(R.string.PuregramDeleteData))
                .setMessage(PuregramRules.str(R.string.PuregramDeleteBody))
                .setPositiveButton(PuregramRules.str(R.string.PuregramDeleteRequest),
                        (d, w) -> PuregramRules.getInstance().requestErasure(currentAccount, effective -> {
                            refresh();
                            showToast(PuregramRules.str(effective == null
                                    ? R.string.PuregramDeleteFailed
                                    : R.string.PuregramDeleteRequested));
                        }))
                .setNegativeButton(PuregramRules.str(R.string.PuregramCancel),
                        (d, w) -> d.dismiss())
                .create());
    }

    private void showToast(String message) {
        if (getParentActivity() != null) {
            android.widget.Toast.makeText(getParentActivity(), message,
                    android.widget.Toast.LENGTH_SHORT).show();
        }
    }

    private static String displayName(PuregramRules.Rule rule) {
        return TextUtils.isEmpty(rule.title) ? rule.identity() : rule.title;
    }

    private static String kindLabel(String kind) {
        if (PuregramRules.KIND_CHANNEL.equals(kind)) {
            return PuregramRules.str(R.string.PuregramKindChannel);
        } else if (PuregramRules.KIND_BOT.equals(kind)) {
            return PuregramRules.str(R.string.PuregramKindBot);
        } else if (PuregramRules.KIND_GROUP.equals(kind)) {
            return PuregramRules.str(R.string.PuregramKindGroup);
        }
        return PuregramRules.str(R.string.PuregramKindUser);
    }

    /** "2026-11-04T…" → "2026-11-04"; the time of day is noise here. */
    private static String formatDate(String iso) {
        if (iso == null) {
            return "";
        }
        int t = iso.indexOf('T');
        return t > 0 ? iso.substring(0, t) : iso;
    }

    private class ListAdapter extends RecyclerListView.SelectionAdapter {

        private final Context mContext;

        ListAdapter(Context context) {
            mContext = context;
        }

        @Override
        public int getItemCount() {
            return rowCount;
        }

        @Override
        public boolean isEnabled(RecyclerView.ViewHolder holder) {
            final int position = holder.getAdapterPosition();
            if (allowedStartRow != -1 && position >= allowedStartRow && position < allowedEndRow) {
                return true;
            }
            if (blockedStartRow != -1 && position >= blockedStartRow && position < blockedEndRow) {
                return true;
            }
            return position == eraseRow || position == addRow;
        }

        @Override
        public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
            View view;
            switch (viewType) {
                case 0:
                    view = new HeaderCell(mContext);
                    view.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    break;
                case 1:
                    view = new TextSettingsCell(mContext);
                    view.setBackgroundColor(Theme.getColor(Theme.key_windowBackgroundWhite));
                    break;
                default:
                    view = new TextInfoPrivacyCell(mContext);
                    break;
            }
            view.setLayoutParams(new RecyclerView.LayoutParams(
                    RecyclerView.LayoutParams.MATCH_PARENT, RecyclerView.LayoutParams.WRAP_CONTENT));
            return new RecyclerListView.Holder(view);
        }

        @Override
        public int getItemViewType(int position) {
            if (position == allowedHeaderRow || position == blockedHeaderRow) {
                return 0;
            }
            if (position == eraseRow || position == addRow) {
                return 1;
            }
            if (allowedStartRow != -1 && position >= allowedStartRow && position < allowedEndRow) {
                return 1;
            }
            if (blockedStartRow != -1 && position >= blockedStartRow && position < blockedEndRow) {
                return 1;
            }
            return 2;
        }

        @Override
        public void onBindViewHolder(RecyclerView.ViewHolder holder, int position) {
            switch (holder.getItemViewType()) {
                case 0: {
                    HeaderCell cell = (HeaderCell) holder.itemView;
                    cell.setText(PuregramRules.str(position == allowedHeaderRow
                            ? R.string.PuregramAllowedSection
                            : R.string.PuregramBlockedSection));
                    break;
                }
                case 1: {
                    TextSettingsCell cell = (TextSettingsCell) holder.itemView;
                    if (position == addRow) {
                        cell.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlueText4));
                        cell.setText(PuregramRules.str(R.string.PuregramAddManually), false);
                        break;
                    }
                    if (position == eraseRow) {
                        cell.setTextColor(Theme.getColor(Theme.key_text_RedRegular));
                        final String pending =
                                PuregramRules.getInstance().erasureEffectiveAt(currentAccount);
                        if (TextUtils.isEmpty(pending)) {
                            cell.setText(PuregramRules.str(R.string.PuregramDeleteData), false);
                        } else {
                            cell.setTextAndValue(
                                    PuregramRules.str(R.string.PuregramDeleteScheduled),
                                    formatDate(pending), false);
                        }
                        break;
                    }
                    cell.setTextColor(Theme.getColor(Theme.key_windowBackgroundWhiteBlackText));
                    final boolean isAllowed = allowedStartRow != -1
                            && position >= allowedStartRow && position < allowedEndRow;
                    final PuregramRules.Rule rule = isAllowed
                            ? allowed.get(position - allowedStartRow)
                            : blocked.get(position - blockedStartRow);
                    final boolean last = isAllowed
                            ? position == allowedEndRow - 1
                            : position == blockedEndRow - 1;
                    cell.setTextAndValue(displayName(rule), kindLabel(rule.kind), !last);
                    break;
                }
                default: {
                    TextInfoPrivacyCell cell = (TextInfoPrivacyCell) holder.itemView;
                    if (position == statusRow) {
                        final String claim = PuregramRules.getInstance().claimPendingUntil();
                        cell.setText(PuregramRules.str(claim != null
                                ? R.string.PuregramClaimPending
                                : R.string.PuregramDefaultsInfo));
                    } else if (position == addInfoRow) {
                        cell.setText(PuregramRules.str(R.string.PuregramAddManuallyInfo));
                    } else if (position == allowedInfoRow) {
                        cell.setText(PuregramRules.str(allowed.isEmpty()
                                ? R.string.PuregramAllowedEmpty
                                : R.string.PuregramAllowedHint));
                    } else if (position == blockedInfoRow) {
                        cell.setText(PuregramRules.str(blocked.isEmpty()
                                ? R.string.PuregramBlockedEmpty
                                : R.string.PuregramBlockedHint));
                    } else {
                        cell.setText(PuregramRules.str(R.string.PuregramDeleteInfo));
                    }
                    break;
                }
            }
        }
    }
}
