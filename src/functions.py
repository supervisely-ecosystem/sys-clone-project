def get_datasets_tree_msg(datasets_tree):

    def _collect_ds_tree_names(ds_tree, level=0):
        msg = ""
        for ds, nested_ds_tree in ds_tree.items():
            msg += "  " * level + f"― {ds.name}\n"
            msg += _collect_ds_tree_names(nested_ds_tree, level + 1)
        return msg

    return _collect_ds_tree_names(datasets_tree)
