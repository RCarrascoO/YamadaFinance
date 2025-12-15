import matplotlib.pyplot as plt
import io

def generate_pie_chart(data: list, title: str) -> io.BytesIO:
    """
    Genera un gráfico de torta a partir de una lista de tuplas (etiqueta, valor).
    Retorna un objeto BytesIO con la imagen PNG.
    """
    if not data:
        return None

    labels = [item[0] if item[0] else "Otros" for item in data]
    sizes = [item[1] for item in data]
    
    # Configuración del gráfico
    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, texts, autotexts = ax.pie(
        sizes, 
        labels=labels, 
        autopct='%1.1f%%',
        startangle=90,
        textprops=dict(color="black")
    )
    
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    plt.title(title)
    
    # Guardar en buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def generate_bar_chart(data: list, title: str, xlabel: str, ylabel: str) -> io.BytesIO:
    """
    Genera un gráfico de barras.
    """
    if not data:
        return None
        
    labels = [item[0] if item[0] else "Otros" for item in data]
    values = [item[1] for item in data]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(labels, values, color='skyblue')
    
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    plt.xticks(rotation=45, ha='right')
    
    # Añadir valores sobre las barras
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'${height:,.0f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    
    return buf

def generate_monthly_trend_chart(data: list, year: int) -> io.BytesIO:
    """
    Genera un gráfico de línea con la tendencia mensual.
    data: lista de tuplas (mes_numero, total)
    """
    # Rellenar meses faltantes con 0
    monthly_totals = {m: 0 for m in range(1, 13)}
    for month, total in data:
        monthly_totals[int(month)] = total
        
    months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    values = [monthly_totals[i] for i in range(1, 13)]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Gráfico de línea con puntos
    ax.plot(months, values, marker='o', linestyle='-', color='#2ecc71', linewidth=2, markersize=8)
    
    # Rellenar área bajo la curva
    ax.fill_between(months, values, color='#2ecc71', alpha=0.1)
    
    ax.set_title(f"Tendencia de Gastos - {year}", fontsize=14, pad=20)
    ax.set_ylabel("Monto ($)")
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # Añadir etiquetas de valor en los puntos (solo si > 0)
    for i, v in enumerate(values):
        if v > 0:
            ax.annotate(f'${v/1000:.0f}k', 
                        xy=(i, v), 
                        xytext=(0, 10), 
                        textcoords='offset points', 
                        ha='center', 
                        fontsize=9,
                        fontweight='bold')
            
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    
    return buf
