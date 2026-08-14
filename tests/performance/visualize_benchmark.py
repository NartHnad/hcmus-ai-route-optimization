import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def main():
    # Định vị thư mục results
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    results_dir = os.path.join(base_dir, "results")
    
    search_csv = os.path.join(results_dir, "benchmark_search_summary.csv")
    optim_csv = os.path.join(results_dir, "benchmark_optimization_summary.csv")
    
    if not os.path.exists(results_dir):
        print(f"[Lỗi] Không tìm thấy thư mục results tại: {results_dir}")
        return
        
    sns.set_theme(style="whitegrid")
    
    # ==========================================
    # 1. Vẽ biểu đồ cho Point-to-Point Search
    # ==========================================
    if os.path.exists(search_csv):
        df_search = pd.read_csv(search_csv)
        if not df_search.empty:
            print("Đang vẽ biểu đồ cho Point-to-Point Search...")
            
            # --- Biểu đồ Thời gian chạy (Avg Time) ---
            plt.figure(figsize=(10, 6))
            sns.barplot(data=df_search, x="Algorithm", y="Avg_Time_ms", hue="Scenario")
            plt.title("Search Algorithms: Average Execution Time (ms)", fontsize=14, fontweight='bold')
            plt.ylabel("Time (ms)")
            plt.xlabel("Algorithm")
            plt.xticks(rotation=15)
            plt.tight_layout()
            plt.savefig(os.path.join(results_dir, "chart_search_time.png"), dpi=300)
            plt.close()
            
            # --- Biểu đồ Tiêu thụ Bộ nhớ (Peak Memory) ---
            plt.figure(figsize=(10, 6))
            sns.barplot(data=df_search, x="Algorithm", y="Avg_Peak_Memory_KB", hue="Scenario")
            plt.title("Search Algorithms: Peak Memory Usage (KB)", fontsize=14, fontweight='bold')
            plt.ylabel("Memory (KB)")
            plt.xlabel("Algorithm")
            plt.xticks(rotation=15)
            plt.tight_layout()
            plt.savefig(os.path.join(results_dir, "chart_search_memory.png"), dpi=300)
            plt.close()

            # --- Biểu đồ Tỷ lệ Thành công (Success Rate) ---
            plt.figure(figsize=(10, 6))
            sns.barplot(data=df_search, x="Algorithm", y="Success_Rate_%", hue="Scenario")
            plt.title("Search Algorithms: Success Rate (%)", fontsize=14, fontweight='bold')
            plt.ylabel("Success Rate (%)")
            plt.xlabel("Algorithm")
            plt.ylim(0, 105)
            plt.xticks(rotation=15)
            plt.tight_layout()
            plt.savefig(os.path.join(results_dir, "chart_search_success_rate.png"), dpi=300)
            plt.close()
            
            print(" -> Đã lưu: chart_search_time.png, chart_search_memory.png, chart_search_success_rate.png")
            
    # ==========================================
    # 2. Vẽ biểu đồ cho Multi-Location Optimization
    # ==========================================
    if os.path.exists(optim_csv):
        df_optim = pd.read_csv(optim_csv)
        if not df_optim.empty:
            print("Đang vẽ biểu đồ cho Multi-Location Optimization...")
            
            # --- Biểu đồ Thời gian chạy (Avg Time) ---
            plt.figure(figsize=(10, 6))
            sns.barplot(data=df_optim, x="Algorithm", y="Avg_Time_ms", hue="Scenario")
            plt.title("Optimization Algorithms: Average Execution Time (ms)", fontsize=14, fontweight='bold')
            plt.ylabel("Time (ms)")
            plt.xlabel("Algorithm")
            plt.tight_layout()
            plt.savefig(os.path.join(results_dir, "chart_optim_time.png"), dpi=300)
            plt.close()
            
            # --- Biểu đồ Tỷ lệ Thành công (Success Rate) ---
            plt.figure(figsize=(10, 6))
            sns.barplot(data=df_optim, x="Algorithm", y="Success_Rate_%", hue="Scenario")
            plt.title("Optimization Algorithms: Success Rate (%)", fontsize=14, fontweight='bold')
            plt.ylabel("Success Rate (%)")
            plt.xlabel("Algorithm")
            plt.ylim(0, 105)
            plt.tight_layout()
            plt.savefig(os.path.join(results_dir, "chart_optim_success_rate.png"), dpi=300)
            plt.close()
            
            print(" -> Đã lưu: chart_optim_time.png, chart_optim_success_rate.png")
            
    print("\nHoàn tất! Các file hình ảnh (.png) đã được lưu vào thư mục results/.")

if __name__ == "__main__":
    main()
