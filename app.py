# 1. Mostramos la tabla
        df_editado = st.data_editor(
            df_i[[c for c in cols_to_show if c in df_i.columns]],
            column_config={
                "id": None, 
                "foto_path": st.column_config.ImageColumn("Imagen"),
                "precio_inv": st.column_config.NumberColumn("Inv ($)", format="$%.2f"),
                "precio_pub": st.column_config.NumberColumn("Pub ($)", format="$%.2f")
            },
            hide_index=False, # ESTO DEBE SER FALSE PARA PODER HACER CLIC
            use_container_width=True,
            disabled=True if role == "equipo" else False,
            key="editor_central"
        )

        # 2. Leemos la selección (IMPORTANTE)
        state = st.session_state.get("editor_central")
        selected_rows = []
        if state and "selection" in state:
            selected_rows = state["selection"].get("rows", [])

        # 3. Si hay algo seleccionado, mostramos los botones
        if selected_rows:
            st.markdown("---")
            # Obtenemos los datos de la fila seleccionada
            idx_sel = selected_rows[0]
            item_sel = df_i.iloc[idx_sel]
            
            st.subheader(f"🛠️ Acciones para: {item_sel['nombre']}")
            # Aquí aparecen tus botones de eliminar y cambiar imagen...
