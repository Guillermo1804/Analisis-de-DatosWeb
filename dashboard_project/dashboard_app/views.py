# dashboard_app/views.py
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.views.decorators.http import require_POST
from .forms import UploadDatasetForm
from .models import Dataset
import pandas as pd
import numpy as np

def upload_csv(request):
    """
    Subir un CSV y guardarlo como Dataset (modelo).
    También lista los datasets subidos.
    """
    if request.method == 'POST':
        form = UploadDatasetForm(request.POST, request.FILES)
        if form.is_valid():
            ds = form.save(commit=False)
            # nombre legible (puede ser file.name o mejorar)
            ds.name = request.FILES['file'].name
            ds.save()
            # Guardar id en sesión para UX (opcional)
            request.session['uploaded_dataset_id'] = ds.id
            return redirect('dashboard_app:preview_dataset', pk=ds.id)
    else:
        form = UploadDatasetForm()

    datasets = Dataset.objects.all().order_by('-uploaded_at')
    return render(request, 'dashboard_app/upload.html', {
        'form': form,
        'datasets': datasets,
    })


def _to_py_val(v):
    """Convierte valores de pandas/numpy a tipos Python serializables (None/int/float/str)."""
    if pd.isna(v):
        return None
    # numpy scalar -> Python native
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    # Python types
    if isinstance(v, (int, float, str, bool)):
        return v
    try:
        return float(v)
    except Exception:
        return str(v)


def preview_dataset(request, pk):
    """
    Preview del dataset identificado por pk (Dataset model).
    Genera: head_html, rows_info, numeric_stats, numeric_values (para histogramas).
    """
    dataset = get_object_or_404(Dataset, pk=pk)
    uploaded_path = dataset.file.path
    uploaded_name = dataset.name

    # leer una muestra para tipos y primeros registros
    sample_rows = 1000
    try:
        df_sample = pd.read_csv(uploaded_path, nrows=sample_rows, low_memory=False)
    except Exception as e:
        return render(request, 'dashboard_app/preview.html', {'error': f'Error leyendo el CSV: {e}'})

    columns = list(df_sample.columns)
    dtypes = df_sample.dtypes.apply(str).to_dict()
    head_html = df_sample.head(10).to_html(classes="table table-sm", index=False, escape=False)

    # contar filas y nulos por chunks (para archivos grandes)
    chunksize = 200_000
    total_rows = 0
    null_counts = None
    try:
        for chunk in pd.read_csv(uploaded_path, chunksize=chunksize, low_memory=False):
            total_rows += len(chunk)
            null_counts = chunk.isnull().sum() if null_counts is None else null_counts.add(chunk.isnull().sum(), fill_value=0)
    except pd.errors.EmptyDataError:
        total_rows = 0
        null_counts = pd.Series(dtype=int)
    except Exception:
        # fallback: leer todo
        df_all = pd.read_csv(uploaded_path, low_memory=False)
        total_rows = len(df_all)
        null_counts = df_all.isnull().sum()

    null_counts = null_counts.fillna(0).astype(int).to_dict()

    rows_info = [
        {"name": col, "dtype": dtypes[col], "nulls": null_counts.get(col, 0)}
        for col in columns
    ]

    # Estadísticas y valores para histogramas (solo de la muestra)
    numeric_stats = []
    numeric_values = {}
    numeric_df = df_sample.select_dtypes(include='number')
    if not numeric_df.empty:
        stats_df = numeric_df.describe().T
        for col in numeric_df.columns:
            mode_val = numeric_df[col].mode()
            stats_df.loc[col, 'mode'] = mode_val.iloc[0] if not mode_val.empty else None

        for col in stats_df.index:
            numeric_stats.append({
                'column': col,
                'count': int(stats_df.loc[col, 'count']),
                'mean': _to_py_val(stats_df.loc[col, 'mean']),
                'std': _to_py_val(stats_df.loc[col, 'std']),
                'min': _to_py_val(stats_df.loc[col, 'min']),
                'q25': _to_py_val(stats_df.loc[col, '25%']),
                'q50': _to_py_val(stats_df.loc[col, '50%']),
                'q75': _to_py_val(stats_df.loc[col, '75%']),
                'max': _to_py_val(stats_df.loc[col, 'max']),
                'mode': _to_py_val(stats_df.loc[col, 'mode'])
            })

            # para histogramas: tomar muestra si muy grande
            vals = numeric_df[col].dropna()
            if len(vals) > 10000:
                vals = vals.sample(10000, random_state=0)
            # convertir a floats para JS
            numeric_values[col] = [float(x) for x in vals.tolist()]

    context = {
        'dataset': dataset,
        'file_name': uploaded_name,
        'total_rows': total_rows,
        'n_columns': len(columns),
        'head_html': head_html,
        'rows_info': rows_info,
        'numeric_stats': numeric_stats,
        'numeric_values': numeric_values,
    }
    return render(request, 'dashboard_app/preview.html', context)


@require_POST
def delete_dataset(request, pk):
    """
    Elimina dataset (archivo y registro DB).
    """
    dataset = get_object_or_404(Dataset, pk=pk)
    # borrar archivo del storage
    try:
        dataset.file.delete(save=False)
    except Exception:
        pass
    dataset.delete()
    # limpiar session si apuntaba a este dataset
    if request.session.get('uploaded_dataset_id') == pk:
        request.session.pop('uploaded_dataset_id', None)
    return redirect('dashboard_app:upload_csv')
